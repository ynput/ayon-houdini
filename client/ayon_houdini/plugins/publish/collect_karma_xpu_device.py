import pyblish.api

from ayon_core.pipeline.publish import FARM_JOB_ENV_DATA_KEY

from ayon_houdini.api import plugin


class CollectKarmaXPUDevice(plugin.HoudiniInstancePlugin):
    """Collect farm job environment to restrict the Karma XPU devices.
    """

    # runs after `CollectFarmInstances` so `farm` is collected.
    order = pyblish.api.CollectorOrder
    label = "Collect Karma XPU Device"
    families = ["karma_rop", "usdrender"]

    def process(self, instance):
        creator_attribute = instance.data["creator_attributes"]

        if not creator_attribute.get("xpu_disable_cpu"):
            return

        if not instance.data.get("farm"):
            self.log.info("Instance doesn't render on farm. "
                           "Skipping Karma XPU device environment.")
            return

        job_env = instance.data.setdefault(FARM_JOB_ENV_DATA_KEY, {})
        job_env["KARMA_XPU_DISABLE_EMBREE_DEVICE"] = "1"
        self.log.info("Karma XPU restricted to GPU devices.")
