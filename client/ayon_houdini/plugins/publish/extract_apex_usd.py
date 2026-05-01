import os
import pyblish.api

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

        staging_dir = instance.data.get("stagingDir")
        layer_path = os.path.join(staging_dir, f"{instance.name}.usd")

        sdf_layer = Sdf.Layer.CreateNew(layer_path, args={"format": "usda"})
        self.log.debug(f"Creating USD rig layer: {sdf_layer}")

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
        rig_attr = Sdf.AttributeSpec(
            asset_prim,
            "ayon:apex_rig",
            Sdf.ValueTypeNames.Asset,
            variability=Sdf.VariabilityUniform
        )
        rig_path = self.get_representation_path_in_publish_context(
            instance
        )
        self.log.debug(f"Setting 'ayon:apex_rig' attr to '{rig_path}'")
        rig_attr.default = Sdf.AssetPath(rig_path)

        # Save the file
        sdf_layer.Save()

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
        if path:
            return path

        raise RuntimeError("Unable to resolve publish path.")
