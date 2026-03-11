import os
import pyblish.api

try:
    from pxr import Sdf
except ImportError:
    Sdf = None

try:
    from ayon_core.pipeline.usdlib import (
        set_layer_defaults,
        get_standard_default_prim_name
    )
except ImportError:
    pass

from ayon_houdini.api import plugin


class CollectAPEXUSD(plugin.HoudiniInstancePlugin):
    """Inject the current working file into context"""

    # Run Before CollectUSDLayerContributions from core plugins
    order = pyblish.api.CollectorOrder + 0.25
    label = "Collect APEX To USD"

    families = ["rig"]

    def process(self, instance):
        """Inject the current working file"""


        folder_path = instance.data["folderPath"]

        default_prim = get_standard_default_prim_name(folder_path)
        sdf_layer = Sdf.Layer.CreateAnonymous()
        set_layer_defaults(sdf_layer, default_prim=default_prim)

        # TODO Add rig output to the usd rig layer.

        # Save the file
        staging_dir = instance.data.get("stagingDir")
        filename = f"{instance.name}.usd"
        filepath = os.path.join(staging_dir, filename)

        self.log.debug(f"Saving rig layer: {filepath}")
        sdf_layer.Export(filepath, args={"format": "usda"})

        representations = instance.data.setdefault("representations", [])
        representations.append({
            "name": "usd",
            "ext": "usd",
            "files": os.path.basename(filepath),
            "stagingDir": os.path.dirname(filepath),
        })
