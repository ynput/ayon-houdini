# -*- coding: utf-8 -*-
"""Creator plugin for creating pubs."""
from ayon_houdini.api import plugin, lib
import json

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
        return [hou.ropNodeTypeCategory()]

    def imprint(self, node, values, update=False):
        # Imprint the value onto existing attributes instead
        # of trying to force create them because the HDA already
        # contains the attributes
        for key, value in values.items():
            parm = node.parm(key)
            if parm:
                if isinstance(value, dict):
                    value = lib.JSON_PREFIX + json.dumps(value)
                parm.set(value)

    def read(self, node):
        # Explicitly read the attributes because the attributes are not
        # spare parms on this HDA
        attributes = [
            # Ordered by appearance in the UI
            "id",
            "productType",
            "active"
            "creator_identifier",
            "variant",
            "folderPath",
            "task",
            "creator_attributes",
            "publish_attributes",
            "AYON_productName",
        ]
        result = {}
        for attr in attributes:

            parm = node.parm(attr)
            if not parm:
                result[attr] = None
                continue
            value = parm.eval()
            if isinstance(value, str) and value.startswith(lib.JSON_PREFIX):
                value = json.loads(value[len(lib.JSON_PREFIX):])
            result[attr] = value

        # Creator attributes and publish attributes must be dict to avoid
        # bugs in publisher UI
        for key in ["creator_attributes", "publish_attributes"]:
            if not result[key]:
                result[key] = {}
        return result