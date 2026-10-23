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
    """Create runtime instances from the expected files of an instance."""

    # Always deep copied from the source instance to runtime instances.
    runtime_instance_transfer_keys = {
        "creator_attributes",
        "publish_attributes",
    }
    # Always passed by reference from the source instance to runtime
    # instances. The entities are safe to share because runtime instances
    # always publish to the same context as their source instance.
    runtime_instance_transfer_transient_data_keys = {
        "instance_node",
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

        This heavily depends on farm logic where expected files.
        Where it creates a runtime instances from "expectedFiles" dict
        in instance data.
            {
                "item_1": ["file1", "file2", ...],
                "item_2": "file",
            }
        Example:
        >>> expected_files = instance.data.setdefault("expectedFiles", list())
        >>> expected_files.append({"cache": files_sequence_list})
        >>> self.create_runtime_instance(instance)

        Notes:
            - If the product base type is render, it creates aov instances.
              Otherwise, it creates cache instances, which expect simpler
              instance data.
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
            transfer_keys (Optional[set[str]]): Extra keys to deep copy
                from the source instance. They are added to the keys that
                are always deep copied, `runtime_instance_transfer_keys`:
                "creator_attributes" and "publish_attributes".
            transfer_transient_data_keys (Optional[set[str]]): Extra keys to
                pass by reference from the source instance. They are added
                to the keys that are always passed by reference,
                `runtime_instance_transfer_transient_data_keys`:
                "instance_node", "projectEntity", "folderEntity" and
                "taskEntity".

        Returns:
                list of pyblish.api.Instance: Instances created from
                    expected files.

        """

        from copy import deepcopy
        from ayon_core.pipeline.farm.pyblish_functions import (
            create_skeleton_instance,
            create_skeleton_instance_cache,
            create_instances_for_aov,
            create_instances_for_cache
        )

        transfer_keys = (
            self.runtime_instance_transfer_keys | set(transfer_keys or ())
        )
        transfer_transient_data_keys = (
            self.runtime_instance_transfer_transient_data_keys
            | set(transfer_transient_data_keys or ())
        )

        # Use same logic as how instances get created for farm submissions
        is_render = instance.data.get("productBaseType") == "render"
        if is_render:
            # It forces the product base type to "render"
            instance_skeleton_data = create_skeleton_instance(
                instance,
                # TODO: These should be fixed in core to just allow the
                #  default None to work
                families_transfer=[],
                instance_transfer={},
            )
        else:
            # It keeps the product base type and product type of the source
            # instance, but it doesn't set the task.
            instance_skeleton_data = create_skeleton_instance_cache(instance)
            instance_skeleton_data["task"] = instance.data.get("task")

        self.post_process_skeleton_data(instance,
                                        instance_skeleton_data,
                                        families_to_append)

        # Runtime instances must follow the context of the source instance
        for key in ("folderPath", "task"):
            if instance_skeleton_data.get(key) != instance.data.get(key):
                raise PublishError(
                    f"Runtime instances must publish to the same '{key}'"
                    f" as their source instance '{instance}'. Change it on"
                    " the source instance instead."
                )

        instances_data = []
        if is_render:
            instances_data = create_instances_for_aov(
                instance=instance,
                skeleton=instance_skeleton_data,
                aov_filter=aov_filter or {},  # Use filter from settings.
                skip_integration_repre_list=[], # Extensions to skip.
                # Only add review if it's enabled on the source instance.
                do_not_add_review=not instance.data.get("review", False),
            )
        else:
            instances_data = create_instances_for_cache(
                instance,
                instance_skeleton_data
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
            families_to_append: Optional[list[str]] = None
        ):
        """Post process skeleton data
        Applies Houdini specific logic to skeleton data.
        Args:
            instance (pyblish.api.Instance): The publish instance.
            instance_skeleton_data (dict): data to modify.
            families_to_append (Optional[list[str]]): Families to add.
        """
        # Remove frame data like frameStart and handleStart
        # as they are added in later publisher plugins
        for key in (
            "frameStart", "frameEnd",
            "handleStart", "handleEnd",
         ):
            instance_skeleton_data.pop(key, None)

        # The skeleton families are only `render` plus `review` for renders,
        #   or `render` plus the product base type for caches.
        if families_to_append:
            instance_skeleton_data["families"].extend(families_to_append)
        instance_skeleton_data.update({
            "frameStartHandle": instance.data["frameStartHandle"],
            "frameEndHandle": instance.data["frameEndHandle"],
        })


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
                "colorspaceConfig",
                "colorspace",
                "colorspaceDisplay",
                "colorspaceView",
            }
        )

        # Skip integrating original render instance.
        # We are not removing it because it's used to trigger the render.
        instance.data["integrate"] = False
