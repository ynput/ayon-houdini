import pyblish.api

from ayon_core.pipeline.publish import (
    get_plugin_settings,
    apply_plugin_settings_automatically,
    ColormanagedPyblishPluginMixin
)
from ayon_houdini.api import plugin
try:
    from ayon_core.pipeline.farm.pyblish_functions import (
        _get_legacy_product_name_and_group,
    )
except ImportError:
    _get_legacy_product_name_and_group = None


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

        # Create Instance for each AOV.
        self.create_runtime_instance(
            instance,
            aov_filter = self.aov_filter,
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
