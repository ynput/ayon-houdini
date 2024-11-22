# -*- coding: utf-8 -*-
"""Creator plugin for creating USDs."""
from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef

import hou


class CreateUSD(plugin.HoudiniCreator):
    """Universal Scene Description"""
    identifier = "io.openpype.creators.houdini.usd"
    label = "USD"
    product_type = "usd"
    icon = "cubes"
    enabled = False
    description = "Create USD"

    # Default render target
    render_target = "local"

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "usd"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super(CreateUSD, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        parms = {
            "lopoutput": "$HIP/pyblish/{}.usd".format(product_name),
            "enableoutputprocessor_simplerelativepaths": False,
        }

        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = [
            "fileperframe",
            # Lock some Avalon attributes
            "productType",
            "id",
        ]
        self.lock_parameters(instance_node, to_lock)

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.lopNodeTypeCategory()
        ]

    def get_publish_families(self):
        return ["usd", "usdrop"]

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
        return attrs + self.get_instance_attr_defs()