# -*- coding: utf-8 -*-
"""Creator plugin for creating pubs."""
from ayon_houdini.api import plugin

import hou


class CreateAyonPub(plugin.HoudiniCreator):
    """Universal Scene Description"""

    identifier = "io.openpype.creators.houdini.pub"
    label = "ayon_pub"
    product_type = "pub"
    icon = "cubes"
    description = "Create ayon pub"

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "ayon_publish"})

        instance = super(CreateAyonPub, self).create(
            product_name, instance_data, pre_create_data
        )

        instance_node = hou.node(instance.get("instance_node"))

        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        # Lock any parameters in this list
        to_lock = [
            "fileperframe",
            # Lock some Avalon attributes
            "productType",
            "id",
        ]
        self.lock_parameters(instance_node, to_lock)

    def get_network_categories(self):
        return [hou.ropNodeTypeCategory(), hou.lopNodeTypeCategory()]

    def get_publish_families(self):
        return ["pub"]
