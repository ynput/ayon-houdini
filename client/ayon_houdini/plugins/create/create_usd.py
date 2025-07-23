# -*- coding: utf-8 -*-
"""Creator plugin for creating USDs."""
import inspect

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
    description = "Create USD for generic use"

    # Default render target
    render_target = "local"

    additional_parameters = {}

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
        parms.update(self.additional_parameters)

        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = [
            # Lock some AYON attributes
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


class CreateUSDModel(CreateUSD):
    identifier = "io.ayon.creators.houdini.model.usd"
    label = "USD Asset Model"
    product_type = "model"
    enabled = True
    description = "Create USD Asset model"

    additional_parameters = {
        # Set the 'default prim' by default to the folder name being
        # published to
        "defaultprim": '/`strsplit(chs("folderPath"), "/", -1)`',
    }

    def get_detail_description(self):
        return inspect.cleandoc("""Publish model in USD data.

        From the Houdini Solaris context (LOPs) this will publish a static
        model. Usually used for publishing geometry into a USD asset using
        the USD contribution workflow.
        """)


class CreateUSDAssembly(CreateUSD):
    identifier = "io.ayon.creators.houdini.assembly.usd"
    label = "USD Asset Assembly"
    product_type = "assembly"
    enabled = True
    description = "Create USD Asset assembly"

    additional_parameters = {
        # Set the 'default prim' by default to the folder name being
        # published to
        "defaultprim": '/`strsplit(chs("folderPath"), "/", -1)`',
    }

    def get_detail_description(self):
        return inspect.cleandoc("""Publish assembly in USD data.

        From the Houdini Solaris context (LOPs) this will publish an assembly
        product. Usually used for publishing multiple referenced USD assets
        grouped together and positioned to make an assembled asset.
        """)


class CreateUSDGroom(CreateUSD):
    identifier = "io.ayon.creators.houdini.groom.usd"
    label = "USD Asset Groom"
    product_type = "groom"
    icon = "scissors"
    enabled = True
    description = "Create USD Asset groom of fur and or hairs"

    additional_parameters = {
        # Set the 'default prim' by default to the folder name being
        # published to
        "defaultprim": '/`strsplit(chs("folderPath"), "/", -1)`',
    }

    def get_detail_description(self):
        return inspect.cleandoc("""Publish groom in USD data.

        From the Houdini Solaris context (LOPs) this will usually publish the
        static groom of fur and or hairs. Usually used to define the base
        groom for a character and then used in the `look` to build the final
        materials.
        """)


class CreateUSDLook(CreateUSD):
    """Universal Scene Description Look"""

    identifier = "io.openpype.creators.houdini.usd.look"
    label = "USD Asset Look"
    product_type = "look"
    icon = "paint-brush"
    enabled = True
    description = "Create USD Asset Look with localized textures"

    additional_parameters = {
        # Set the 'default prim' by default to the folder name being
        # published to
        "defaultprim": '/`strsplit(chs("folderPath"), "/", -1)`',
    }

    def get_detail_description(self):
        return inspect.cleandoc("""Publish looks in USD data.

        From the Houdini Solaris context (LOPs) this will publish the look for
        an asset as a USD file with the used textures.

        Any assets used by the look will be relatively remapped to the USD
        file and integrated into the publish as `resources`.
        """)

    def get_publish_families(self):
        return ["usd", "look", "usdrop"]
