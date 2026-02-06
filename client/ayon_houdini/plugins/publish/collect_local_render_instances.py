import pyblish.api
from ayon_core.pipeline.publish import (
    get_plugin_settings,
    apply_plugin_settings_automatically,
    ColormanagedPyblishPluginMixin
)
from ayon_core.pipeline.farm.pyblish_functions import (
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

        product_base_type = "render"  # is always render

        # Using this minimal version of instance_skeleton_data instead of
        # ayon_core.pipeline.farm.pyblish_functions.create_skeleton_instance
        # Reason: to avoid polluting instance data.
        # Note: Frame data like frameStart and handleStart are added in later publisher plugins
        instance_skeleton_data = {
            "productType": product_base_type,
            "productBaseType": product_base_type,
            "productName": instance.data["productName"],
            "task": instance.data["task"],
            "family": product_base_type,
            "families": ["render.local.hou"],
            "folderPath": instance.data["folderPath"],
            "frameStartHandle": instance.data["frameStartHandle"],
            "frameEndHandle": instance.data["frameEndHandle"],
            "comment": instance.data.get("comment"),
            "multipartExr": instance.data["multipartExr"],
            "creator_attributes": instance.data["creator_attributes"],
            "publish_attributes": instance.data["publish_attributes"],
            
            # Houdini specific data items.
            "instance_node": instance.data["instance_node"],
        }
        
        if instance.data.get("review"):
            instance_skeleton_data["families"].append("review")

        if instance.data.get("renderlayer"):
            instance_skeleton_data["renderlayer"] = instance.data["renderlayer"]

        # Include the instance colorspace information too, because these
        # may represent scene display/view, etc.
        for key in (
                "colorspaceConfig",
                "colorspace",
                "colorspaceDisplay",
                "colorspaceView",
        ):
            if key in instance.data:
                value: str = instance.data[key]
                instance_skeleton_data[key] = value

        # Create Instance for each AOV.
        aov_instances = create_instances_for_aov(
            instance=instance,
            skeleton=instance_skeleton_data,
            aov_filter=self.aov_filter,
            # list of extensions that shouldn't be published
            skip_integration_repre_list=[],
            # Don't explicitly skip review.
            do_not_add_review=False
        )

        # NOTE: The assumption that the output image's colorspace is the
        #   scene linear role may be incorrect. Certain renderers, like
        #   Karma allow overriding explicitly the output colorspace of the
        #   image. Such override are currently not considered since these
        #   would need to be detected in a renderer-specific way and the
        #   majority of production scenarios these would not be overridden.
        # TODO: Support renderer-specific explicit colorspace overrides
        # Add the instances directly to the current publish context

        anatomy = instance.context.data["anatomy"]
        for aov_instance_data in aov_instances:
            # The `create_instances_for_aov` makes some paths rootless paths,
            # like the "stagingDir" for each representation which we will make
            # absolute again.
            for representation in aov_instance_data["representations"]:
                representation["stagingDir"] = anatomy.fill_root(representation["stagingDir"])

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
