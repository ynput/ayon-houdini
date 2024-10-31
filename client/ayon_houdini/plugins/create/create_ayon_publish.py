# -*- coding: utf-8 -*-
"""Creator plugin for creating pubs."""
from ayon_houdini.api import plugin

import hou


class CreateAyonPublishROP(plugin.HoudiniCreator):
    """Universal Scene Description"""

    identifier = "io.openpype.creators.houdini.rop_publish"
    label = "AYON Publish"
    product_type = "rop_publish"  # TODO: Come up with better name
    icon = "cubes"
    description = "Create AYON publish ROP "

    node_type = "ayon_publish"

    def get_network_categories(self):
        return [hou.ropNodeTypeCategory(), hou.lopNodeTypeCategory()]

    def get_publish_families(self):
        return ["rop_publish"]
