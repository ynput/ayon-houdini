# -*- coding: utf-8 -*-
"""Creator plugin for creating USD looks with textures."""
import inspect

from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef

import hou


class CreateUSDLook(plugin.HoudiniCreator):
    """Universal Scene Description Look"""

    identifier = "io.openpype.creators.houdini.usd.look"
    label = "Look"
    product_type = "look"
    icon = "paint-brush"
    enabled = True
    description = "Create USD Look"

    # Default render target
    render_target = "local"

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "usd"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super(CreateUSDLook, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        parms = {
            # keep dynamic link to product name in file path.
            "lopoutput": "{root}/`chs('AYON_productName')`/$OS.usd".format(
                root=hou.text.expandString(self.staging_dir)
            ),
            "enableoutputprocessor_simplerelativepaths": False,

            # Set the 'default prim' by default to the folder name being
            # published to
            "defaultprim": '/`strsplit(chs("folderPath"), "/", -1)`',
        }

        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = [
            "fileperframe",
            # Lock some Avalon attributes
            "family",
            "id",
        ]
        self.lock_parameters(instance_node, to_lock)

    def get_detail_description(self):
        return inspect.cleandoc("""Publish looks in USD data.

        From the Houdini Solaris context (LOPs) this will publish the look for
        an asset as a USD file with the used textures.

        Any assets used by the look will be relatively remapped to the USD
        file and integrated into the publish as `resources`.

        """)

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.lopNodeTypeCategory()
        ]

    def get_publish_families(self):
        return ["usd", "look", "usdrop"]

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