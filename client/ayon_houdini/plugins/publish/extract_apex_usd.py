import os
import pyblish.api
import platform

try:
    from pxr import Sdf
except ImportError:
    Sdf = None

try:
    from ayon_core.pipeline.usdlib import (
        set_layer_defaults,
        get_standard_default_prim_name,
        get_or_define_prim_spec,
    )
except ImportError:
    pass

from ayon_core.pipeline.publish.lib import get_instance_expected_output_path
from ayon_houdini.api.lib import splitext
from ayon_houdini.api import plugin


class ExtractAPEXUSD(plugin.HoudiniInstancePlugin):
    """Extract APEX USD Rig Layer

    Initialize the Rig USD layer and populate the 'ayon:apex_rig' attribute
    to point to the expected APEX Rig bgeo representation path in publish
    context.
    """

    order = pyblish.api.ExtractorOrder
    label = "Extract APEX To USD"

    families = ["rig"]

    def process(self, instance):
        """Inject the current working file"""

        layer_path = instance.data["rig_layer"]
        sdf_layer = Sdf.Layer.OpenAsAnonymous(layer_path)

        folder_path = instance.data["folderPath"]
        default_prim = get_standard_default_prim_name(folder_path)
        set_layer_defaults(sdf_layer, default_prim=default_prim)

        # Add rig attribute to the default prim.
        default_prim_path = Sdf.Path(f"/{default_prim.strip('/')}")
        asset_prim = get_or_define_prim_spec(
            sdf_layer,
            default_prim_path,
            "Xform"
        )
        asset_prim.specifier = Sdf.SpecifierOver
        # "ayon:apex_rig" if apex rig exist:
        #   if it is a path, use it in the file read and add it as asset.
        #   if not load model layer and add it as prop.
        rig_attr = Sdf.AttributeSpec(
            asset_prim,
            "ayon:apex_rig",
            Sdf.ValueTypeNames.String,
            variability=Sdf.VariabilityUniform
        )
        rig_attr.default = self.get_representation_path_in_publish_context(
            instance)

        # Save the file
        self.log.debug(f"Set 'ayon:apex_rig' attr to '{layer_path}'")
        self.log.debug(f"Saving rig layer: {layer_path}")
        sdf_layer.Export(layer_path, args={"format": "usda"})

        representations = instance.data.setdefault("representations", [])
        representations.append({
            "name": "usd",
            "ext": "usd",
            "files": os.path.basename(layer_path),
            "stagingDir": os.path.dirname(layer_path),
        })

    def get_representation_path_in_publish_context(self, instance):
        files = instance.data["frames"]
        first_file = files[0] if isinstance(files, (list, tuple)) else files
        _, ext = splitext(
            first_file, allowed_multidot_extensions=[
                ".ass.gz", ".bgeo.sc", ".bgeo.gz",
                ".bgeo.lzma", ".bgeo.bz2"]
        )
        ext = ext.lstrip(".")

        version_name = instance.data["version"]
        specific_version = isinstance(version_name, int)
        path = get_instance_expected_output_path(
            instance,
            representation_name="bgeo",
            ext=ext,
            version=version_name if specific_version else None
        )
        # Ensure `None` for now is also a string
        path = str(path)
        path = os.path.normpath(path)
        if platform.system().lower() == "windows":
            path = path.replace("\\", "/")
        return path
