# -*- coding: utf-8 -*-
"""Creator plugin for creating composite sequences."""
from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatorError

import hou


class CreateCopernicusROP(plugin.HoudiniCreator):
    """Copernicus ROP to Image Sequence"""

    identifier = "io.ayon.creators.houdini.copernicus"
    label = "Composite (Copernicus)"
    description = "Render using the Copernicus Image ROP."
    product_type = "render"
    icon = "fa5.eye"

    ext = ".exr"

    def create(self, product_name, instance_data, pre_create_data):
        instance_data["node_type"] = "image"

        instance = super().create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))
        filepath = "{}{}".format(
            hou.text.expandString("$HIP/pyblish/"),
            "{}.$F4{}".format(product_name, self.ext)
        )
        parms = {
            "trange": 1,
            "copoutput": filepath
        }
        if self.selected_nodes:
            if len(self.selected_nodes) > 1:
                raise CreatorError("More than one item selected.")
            path = self.selected_nodes[0].path()
            parms["coppath"] = path

        instance_node.setParms(parms)

        # Manually set f1 & f2 to $FSTART and $FEND respectively
        # to match other Houdini nodes default.
        instance_node.parm("f1").setExpression("$FSTART")
        instance_node.parm("f2").setExpression("$FEND")

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.cop2NodeTypeCategory()
        ]

    def get_publish_families(self):
        return [
            "render",
            "image_rop",
        ]
