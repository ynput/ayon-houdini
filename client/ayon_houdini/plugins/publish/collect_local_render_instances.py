from typing import Optional

import pyblish.api

from ayon_core.pipeline import PublishError
from ayon_core.pipeline.publish import (
    get_plugin_settings,
    apply_plugin_settings_automatically,
    ColormanagedPyblishPluginMixin
)
from ayon_houdini.api import plugin


# NOTE: This mixin lives next to `CollectLocalRenderInstances` because it is
#   its only user. Move it to `ayon_houdini.api.plugin` (or core) when another
#   plugin needs it.
class RuntimeInstancesMixin(ColormanagedPyblishPluginMixin):
    """Create runtime instances from the expected files of a render instance.
    """

    # Always deep copied from the source instance to runtime instances.
    runtime_instance_transfer_keys = {
        "creator_attributes",
        "publish_attributes",
    }
    # Always passed by reference from the source instance to runtime
    # instances. The entities are safe to share because runtime instances
    # always publish to the same context as their source instance.
    runtime_instance_transfer_transient_data_keys = {
        "projectEntity",
        "folderEntity",
        "taskEntity",
    }

    def create_runtime_instance(
            self,
            instance: pyblish.api.Instance,
            families_to_append: Optional[list[str]] = None,
            aov_filter: Optional[dict] = None,
            transfer_keys: Optional[set[str]] = None,
            transfer_transient_data_keys: Optional[set[str]] = None,
        ):
        """Create Runtime Instances.

        Creates one runtime instance per AOV from the "expectedFiles" of a
        render instance, with the same core functions that are used for
        farm publishing.
            {
                "beauty": ["file1", "file2", ...],
                "N": "file",
            }
        Example:
        >>> expected_files = instance.data.setdefault("expectedFiles", list())
        >>> expected_files.append({"beauty": files_sequence_list})
        >>> self.create_runtime_instance(instance)

        Notes:
            - Only instances with "render" product base type are supported,
              a `PublishError` is raised for others.
            - Runtime instances always publish to the same context (folder
              and task) as their source instance. To publish them elsewhere,
              change the context of the source instance before calling this.

        Args:
            instance (pyblish.api.Instance): Source publish instance.
            families_to_append (Optional[list[str]]): Families to add to
                new instances.
            aov_filter (Optional[dict]): AOV filter as `match_aov_pattern`
                expects it, `{host_name: [regex, ...]}`. It is used for
                generating review if the aov regex matches the filename.
                Empty by default, so only multipart EXRs get a review.
            transfer_keys (Optional[set[str]]): Extra keys to deep copy
                from the source instance. They are added to the keys that
                are always deep copied, `runtime_instance_transfer_keys`:
                "creator_attributes" and "publish_attributes".
            transfer_transient_data_keys (Optional[set[str]]): Extra keys to
                pass by reference from the source instance. They are added
                to the keys that are always passed by reference,
                `runtime_instance_transfer_transient_data_keys`:
                "projectEntity", "folderEntity" and "taskEntity".

        Returns:
                list of pyblish.api.Instance: Instances created from
                    expected files.

        """

        from copy import deepcopy
        from ayon_core.pipeline.farm.pyblish_functions import (
            create_skeleton_instance,
            create_instances_for_aov,
        )

        if instance.data.get("productBaseType") != "render":
            raise PublishError(
                "Runtime instances can only be created from render"
                f" instances. Instance '{instance}' has product base type"
                f" '{instance.data.get('productBaseType')}'."
            )

        transfer_keys = (
            self.runtime_instance_transfer_keys | set(transfer_keys or ())
        )
        transfer_transient_data_keys = (
            self.runtime_instance_transfer_transient_data_keys
            | set(transfer_transient_data_keys or ())
        )

        # Use same logic as how instances get created for farm submissions
        instance_skeleton_data = create_skeleton_instance(
            instance,
            # TODO: These should be fixed in core to just allow the
            #  default None to work
            families_transfer=[],
            instance_transfer={},
        )

        # The skeleton families are only `render` plus `review`.
        if families_to_append:
            instance_skeleton_data["families"].extend(families_to_append)

        self.post_process_skeleton_data(instance, instance_skeleton_data)

        # Runtime instances must follow the context of the source instance
        for key in ("folderPath", "task"):
            if instance_skeleton_data.get(key) != instance.data.get(key):
                raise PublishError(
                    f"Runtime instances must publish to the same '{key}'"
                    f" as their source instance '{instance}'. Change it on"
                    " the source instance instead."
                )

        instances_data = create_instances_for_aov(
            instance=instance,
            skeleton=instance_skeleton_data,
            aov_filter=aov_filter or {},  # Use filter from settings.
            skip_integration_repre_list=[], # Extensions to skip.
            # Only add review if it's enabled on the source instance.
            do_not_add_review=not instance.data.get("review", False),
        )

        # Create instances for each AOV
        aov_instances = []
        anatomy = instance.context.data["anatomy"]
        for aov_instance_data in instances_data:

            # Copy instance data to AOV instances after creation
            for key in transfer_keys:
                if key in instance.data:
                    aov_instance_data[key] = deepcopy(instance.data[key])

            for key in transfer_transient_data_keys:
                if key in instance.data:
                    aov_instance_data[key] = instance.data[key]

            # The `create_instances_for_aov` makes some paths rootless paths,
            # like the "stagingDir" for each representation which we will make
            # absolute again.
            for representation in aov_instance_data["representations"]:
                representation["stagingDir"] = anatomy.fill_root(
                    representation["stagingDir"]
                )

                # Set the colorspace for the representation
                if "colorspace" in instance.data:
                    self.set_representation_colorspace(
                        representation,
                        instance.context,
                        colorspace=instance.data["colorspace"],
                    )

            aov_instance = instance.context.create_instance(
                aov_instance_data["productName"]
            )
            aov_instance.data.update(aov_instance_data)
            aov_instances.append(aov_instance)

        return aov_instances

    def post_process_skeleton_data(
            self,
            instance: pyblish.api.Instance,
            instance_skeleton_data: dict,
        ):
        """Apply DCC specific changes to the skeleton data.

        Called by `create_runtime_instance` after the skeleton data is
        created and before the runtime instances are created from it.
        Override it in the plugin to apply DCC specific logic.

        It must not change "folderPath" or "task", runtime instances
        always publish to the same context as their source instance.

        Args:
            instance (pyblish.api.Instance): Source publish instance.
            instance_skeleton_data (dict): Skeleton data to modify.

        """
        pass


class CollectLocalRenderInstances(RuntimeInstancesMixin,
                                  plugin.HoudiniInstancePlugin):
    """Collect instances for local render.

    Agnostic Local Render Collector.
    """

    # this plugin runs after Collect Render Colorspace
    order = pyblish.api.CollectorOrder + 0.151
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender"]

    label = "Collect local render instances"

    use_deadline_aov_filter = False
    aov_filter = {"host_name": "houdini",
                  "value": [".*([Bb]eauty).*"]}

    @classmethod
    def apply_settings(cls, project_settings):
        # Preserve automatic settings applying logic
        settings = get_plugin_settings(plugin=cls,
                                       project_settings=project_settings,
                                       log=cls.log,
                                       category="houdini")
        apply_plugin_settings_automatically(cls, settings, logger=cls.log)

        if not cls.use_deadline_aov_filter:
            # get aov_filter from collector settings
            # and restructure it as match_aov_pattern requires.
            cls.aov_filter = {
                cls.aov_filter["host_name"]: cls.aov_filter["value"]
            }
        else:
            # get aov_filter from deadline settings
            cls.aov_filter = (
                project_settings
                ["deadline"]
                ["publish"]
                ["ProcessSubmittedJobOnFarm"]
                ["aov_filter"]
            )
            cls.aov_filter = {
                item["name"]: item["value"]
                for item in cls.aov_filter
            }

    def process(self, instance):

        if instance.data["farm"]:
            self.log.debug("Render on farm is enabled. "
                           "Skipping local render collecting.")
            return

        if not instance.data.get("expectedFiles"):
            self.log.warning(
                "Missing collected expected files. "
                "This may be due to misconfiguration of the ROP node, "
                "like pointing to an invalid LOP or SOP path")
            return

        # Create Instance for each AOV.
        self.create_runtime_instance(
            instance,
            aov_filter=self.aov_filter,
            transfer_transient_data_keys={
                "instance_node",
                "colorspaceConfig",
                "colorspace",
                "colorspaceDisplay",
                "colorspaceView",
            }
        )

        # Skip integrating original render instance.
        # We are not removing it because it's used to trigger the render.
        instance.data["integrate"] = False

    def post_process_skeleton_data(
            self,
            instance: pyblish.api.Instance,
            instance_skeleton_data: dict,
        ):
        # The skeleton gets its frame data from
        #   `get_time_data_from_instance_or_context`, which falls back to
        #   the context frame range because Houdini instances only have
        #   `frameStartHandle` and `frameEndHandle` (the ROP frame range)
        #   at this point. `frameStart`, `frameEnd` and the handles are
        #   collected later by `CollectAssetHandles`.
        for key in (
            "frameStart", "frameEnd",
            "handleStart", "handleEnd",
        ):
            instance_skeleton_data.pop(key, None)

        instance_skeleton_data.update({
            "frameStartHandle": instance.data["frameStartHandle"],
            "frameEndHandle": instance.data["frameEndHandle"],
        })
