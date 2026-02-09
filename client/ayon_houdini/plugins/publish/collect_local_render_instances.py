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

    # Non-picklable instance data to transfer to AOV instances.
    transfer_keys = {}

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
        # Remove frame data like frameStart and handleStart
        # as they are added in later publisher plugins
        instance_skeleton_data.pop("frameStart")
        instance_skeleton_data.pop("frameEnd")
        instance_skeleton_data.pop("handleStart")
        instance_skeleton_data.pop("handleEnd")

        # `create_skeleton_instance` only adds `render` and `review`
        # Houdini local render also needs `render.local.hou`
        instance_skeleton_data["families"].append("render.local.hou")
        instance_skeleton_data.update({
            "frameStartHandle": instance.data["frameStartHandle"],
            "frameEndHandle": instance.data["frameEndHandle"],
            "instance_node": instance.data["instance_node"],
            "creator_attributes": instance.data["creator_attributes"],
            "publish_attributes": instance.data["publish_attributes"],
        })

        # Create Instance for each AOV.
        aov_instances = create_instances_for_aov(
            instance=instance,
            skeleton=instance_skeleton_data,
            aov_filter=self.aov_filter,  # Use specified filter in settings.
            skip_integration_repre_list=[], # Extensions to skip publishing.
            do_not_add_review=False  # Don't explicitly skip review.
        )

        # Add non-picklable instance data to AOV instances after creation
        if self.transfer_keys:
            for aov_instance in aov_instances:
                for key in self.transfer_keys:
                    if key in instance.data:
                        aov_instance[key] = instance.data[key]

        # Create instances for each AOV
        anatomy = instance.context.data["anatomy"]
        for aov_instance_data in aov_instances:
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
