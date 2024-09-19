# -*- coding: utf-8 -*-
import inspect
import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateUsdRenderProducts(plugin.HoudiniInstancePlugin):
    """Validate at least one render product is present"""

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate Render Products"
    actions = [SelectROPAction]

    def get_description(self):
        return inspect.cleandoc(
            """### No Render Products

            The render submission specified no Render Product outputs and
            as such would not generate any rendered files.

            This is usually the case if no Render Settings or Render
            Products were created.

            Make sure to create the Render Settings
            relevant to the renderer you want to use.

            """
        )

    def process(self, instance):

        node_path = instance.data["instance_node"]
        if not instance.data.get("output_node"):

            # Report LOP path parm for better logs
            lop_path_parm = hou.node(node_path).parm("loppath")
            if lop_path_parm:
                value = lop_path_parm.evalAsString()
                self.log.warning(
                    f"ROP node 'loppath' parm is set to: '{value}'")

            raise PublishValidationError(
                f"No valid LOP path configured on ROP "
                f"'{node_path}'.",
                title="Invalid LOP path")

        if not instance.data.get("files", []):
            node = hou.node(node_path)
            rendersettings_path = (
                node.evalParm("rendersettings") or "/Render/rendersettings"
            )
            raise PublishValidationError(
                message=(
                    "No Render Products found in Render Settings "
                    "for '{}' at '{}'".format(node_path, rendersettings_path)
                ),
                description=self.get_description(),
                title=self.label
            )
