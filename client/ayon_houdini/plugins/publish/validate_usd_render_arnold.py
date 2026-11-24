# -*- coding: utf-8 -*-
import hou
import pxr
import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateUSDRenderArnoldSettings(plugin.HoudiniInstancePlugin):
    """Validate USD Render Product names are correctly set absolute paths."""

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render Arnold Settings"
    actions = [SelectROPAction]

    def process(self, instance):

        rop_node = hou.node(instance.data["instance_node"])
        node = instance.data.get("output_node")
        if not node:
            # No valid output node was set. We ignore it since it will
            # be validated by another plug-in.
            return

        # Check only for Arnold renderer
        renderer = rop_node.evalParm("renderer")
        if renderer != "HdArnoldRendererPlugin":
            self.log.debug("Skipping Arnold Settings validation because "
                           "renderer is set to: %s", renderer)
            return

        # Validate Arnold Product Type is enabled on the Arnold Render Settings
        # This is confirmed by the `includeAovs` attribute on the RenderProduct
        stage: pxr.Usd.Stage = instance.data["stage"]
        invalid = False
        for prim_path in instance.data.get("usdRenderProducts", []):
            prim = stage.GetPrimAtPath(prim_path)
            include_aovs = prim.GetAttribute("includeAovs")
            if not include_aovs.IsValid() or not include_aovs.Get(0):
                self.log.error(
                    "All Render Products must be set to 'Arnold Product "
                    "Type' on the Arnold Render Settings node to ensure "
                    "correct output of metadata and AOVs."
                )
                invalid = True
                break

        # Ensure 'Delegate Products' is enabled for Husk
        if not rop_node.evalParm("husk_delegateprod"):
            invalid = True
            self.log.error("USD Render ROP has `Husk > Rendering > Delegate "
                           "Products` disabled. Please enable to ensure "
                           "correct output files")

        # TODO: Detect bug of invalid Cryptomatte state?
        # Detect if any Render Products were set that do not actually exist
        # (e.g. invalid rendervar targets for a renderproduct) because that
        # is what originated the Cryptomatte enable->disable bug.

        if invalid:
            raise PublishValidationError(
                "Invalid Render Settings for Arnold render."
            )
