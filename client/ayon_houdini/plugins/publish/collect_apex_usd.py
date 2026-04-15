import pyblish.api

try:
    from pxr import Sdf
except ImportError:
    Sdf = None

from ayon_houdini.api import plugin


class CollectAPEXUSD(plugin.HoudiniInstancePlugin):
    """Collect APEX USD Rig Layer

    Create Empty USD Rig layer"""

    # Run Before CollectUSDLayerContributions from core plugins
    order = pyblish.api.CollectorOrder + 0.25
    label = "Collect APEX To USD"

    families = ["rig"]

    def process(self, instance):
        sdf_layer = Sdf.Layer.CreateAnonymous()
        self.log.debug(f"Creating USD rig layer: {sdf_layer}")
        instance.data["rig_layer"] = sdf_layer
