from copy import deepcopy
import pyblish.api
from ayon_core.pipeline.publish import (
    get_plugin_settings,
    apply_plugin_settings_automatically,
    ColormanagedPyblishPluginMixin
)
from ayon_core.pipeline.farm.pyblish_functions import (
    create_skeleton_instance,
    create_instances_for_aov
)
from ayon_houdini.api import plugin


class CollectLocalRenderInstances(plugin.HoudiniInstancePlugin,
                                  ColormanagedPyblishPluginMixin):
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

    # These will be safely deep copied
    transfer_keys = {
        "creator_attributes",
        "publish_attributes"
    }
    # These will transfer, but won't be a unique copy
    # and are passed by reference.
    transfer_transient_data_keys = {
        "instance_node"
    }

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

        # Use same logic as how instances get created for farm submissions
        instance_skeleton_data =  create_skeleton_instance(
            instance,
            # TODO: These should be fixed in core to just allow the default
            #  None to work
            families_transfer=[],
            instance_transfer={},
        )

        self.post_process_skeleton_data(instance, instance_skeleton_data)

        # Create Instance for each AOV.
        aov_instances = create_instances_for_aov(
            instance=instance,
            skeleton=instance_skeleton_data,
            aov_filter=self.aov_filter,  # Use specified filter in settings.
            skip_integration_repre_list=[], # Extensions to skip publishing.
            do_not_add_review=False  # Don't explicitly skip review.
        )

        # Create instances for each AOV
        anatomy = instance.context.data["anatomy"]
        for aov_instance_data in aov_instances:
            # Copy instance data to AOV instances after creation
            for key in self.transfer_keys:
                if key in instance.data:
                    aov_instance_data[key] = deepcopy(instance.data[key])

            for key in self.transfer_transient_data_keys:
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

        # Skip integrating original render instance.
        # We are not removing it because it's used to trigger the render.
        instance.data["integrate"] = False

    def post_process_skeleton_data(
            instance: pyblish.api.Instance,
            instance_skeleton_data: dict
        ):
        """Post process skeleton data

        Applies Houdini specific logic to skeleton data.
        Args:
            instance (pyblish.api.Instance): The publish instance.
            instance_skeleton_data (dict): data to modify.
        """

        # Remove frame data like frameStart and handleStart
        # as they are added in later publisher plugins
        for key in (
            "frameStart", "frameEnd",
            "handleStart", "handleEnd",
        ):
            instance_skeleton_data.pop(key, None)

        # `create_skeleton_instance` only adds `render` and `review`
        # Houdini local render also needs `render.local.hou`
        instance_skeleton_data["families"].append("render.local.hou")
        instance_skeleton_data.update({
            "frameStartHandle": instance.data["frameStartHandle"],
            "frameEndHandle": instance.data["frameEndHandle"],
        })
