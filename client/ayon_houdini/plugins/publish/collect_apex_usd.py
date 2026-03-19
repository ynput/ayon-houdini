import os
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

        # Save the file
        staging_dir = instance.data.get("stagingDir")
        filename = f"{instance.name}.usd"
        filepath = os.path.join(staging_dir, filename)

        self.log.debug(f"Saving rig layer: {filepath}")
        sdf_layer.Export(filepath, args={"format": "usda"})

        instance.data["rig_layer"] = filepath
