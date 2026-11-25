import hou
import pyblish.api

from ayon_core.pipeline import OptionalPyblishPluginMixin
from ayon_core.pipeline.publish import FARM_JOB_ENV_DATA_KEY

from ayon_houdini.api import plugin


class CollectKarmaXPUDisableCPU(plugin.HoudiniInstancePlugin,
                               OptionalPyblishPluginMixin):
    """Collect farm job environment to restrict the Karma XPU devices.

    When active, `KARMA_XPU_DISABLE_EMBREE_DEVICE=1` is added to the farm
    job environment so Karma XPU renders on GPU devices only. Only Karma
    XPU reads this variable, other renderers ignore it.
    """

    # runs after `CollectFarmInstances` so `farm` is collected.
    order = pyblish.api.CollectorOrder
    label = "Disable CPU (Karma XPU)"
    families = ["karma_rop", "usdrender"]
    optional_tooltip = (
        "Disable the Embree (CPU) device so Karma XPU renders on GPU "
        "devices only.\n"
        "Sets KARMA_XPU_DISABLE_EMBREE_DEVICE=1 in the farm job "
        "environment. Only affects farm renders."
    )

    @classmethod
    def get_attr_defs_for_instance(cls, create_context, instance):
        # Show the toggle only when the node renders with Karma XPU.
        # Changing the renderer on the node needs a publisher refresh.
        if not cls.instance_matches_plugin_families(instance):
            return []
        if not cls.is_karma_xpu(instance["instance_node"]):
            return []
        return cls.get_attribute_defs()

    @staticmethod
    def is_karma_xpu(node_path):
        """Return whether the ROP at `node_path` renders with Karma XPU."""
        node = hou.node(node_path)
        if node.type().name() == "karma":
            return node.evalParm("engine") == "xpu"
        return node.evalParm("renderer") == "BRAY_HdKarmaXPU"

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if not instance.data.get("farm"):
            self.log.info("Instance doesn't render on farm. "
                           "Skipping Karma XPU device environment.")
            return

        # The toggle is hidden for other renderers, but `is_active` can
        # still pass there as it falls back to the settings default.
        if not self.is_karma_xpu(instance.data["instance_node"]):
            self.log.debug("Renderer isn't Karma XPU. Skipping.")
            return

        job_env = instance.data.setdefault(FARM_JOB_ENV_DATA_KEY, {})
        job_env["KARMA_XPU_DISABLE_EMBREE_DEVICE"] = "1"
        self.log.info("Karma XPU restricted to GPU devices.")
