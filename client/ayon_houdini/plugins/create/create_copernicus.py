# -*- coding: utf-8 -*-
"""Creator plugin for creating composite sequences."""
from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatorError
from ayon_core.lib import EnumDef

import hou


class CreateCopernicusROP(plugin.HoudiniCreator):
    """Copernicus ROP to Image Sequence"""

    identifier = "io.ayon.creators.houdini.copernicus"
    label = "Composite (Copernicus)"
    description = "Render using the Copernicus Image ROP"
    product_type = "render"
    icon = "fa5.eye"

    ext = ".exr"

    # Copernicus was introduced in Houdini 20.5 so we only enable this
    # creator if the Houdini version is 20.5 or higher.
    enabled = hou.applicationVersion() >= (20, 5, 0)

    # Default render target
    render_target = "local"

    def create(self, product_name, instance_data, pre_create_data):
        instance_data["node_type"] = "image"

        instance = super().create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))
        parms = {
            "trange": 1,
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

    def set_node_staging_dir(
            self, node, staging_dir, instance, pre_create_data):
        node.parm("copoutput").set(f"{staging_dir}/$OS.$F4{self.ext}")

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.cop2NodeTypeCategory()
        ]

    def get_publish_families(self):
        return [
            "render",
            "image_rop",
            "publish.hou"
        ]
    
    def get_instance_attr_defs(self):
        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
        }

        return [
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()
        # Use same attributes as for instance attributes
        return attrs + self.get_instance_attr_defs()
