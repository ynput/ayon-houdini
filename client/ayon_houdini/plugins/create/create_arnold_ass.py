# -*- coding: utf-8 -*-
"""Creator plugin for creating Arnold ASS files."""
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import get_custom_staging_dir

from ayon_core.lib import EnumDef


class CreateArnoldAss(plugin.HoudiniCreator):
    """Arnold .ass Archive"""

    identifier = "io.openpype.creators.houdini.ass"
    label = "Arnold ASS"
    product_type = "ass"
    icon = "magic"

    # Default extension: `.ass` or `.ass.gz`
    # however calling HoudiniCreator.create()
    # will override it by the value in the project settings
    ext = ".ass"

    # Default render target
    render_target = "local"

    def create(self, product_name, instance_data, pre_create_data):
        import hou

        instance_data.update({"node_type": "arnold"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super(CreateArnoldAss, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        # Hide Properties Tab on Arnold ROP since that's used
        # for rendering instead of .ass Archive Export
        parm_template_group = instance_node.parmTemplateGroup()
        parm_template_group.hideFolder("Properties", True)
        instance_node.setParmTemplateGroup(parm_template_group)

        parms = {
            # Render frame range
            "trange": 1,
            # Arnold ROP settings
            "ar_ass_export_enable": 1
        }
        
        if self.enable_staging_path_management:            
            # keep dynamic link to product name in file path.
            self.staging_dir = get_custom_staging_dir(self.product_type, product_name) or self.staging_dir
            parms["ar_ass_file"] = "{root}/`chs('AYON_productName')`/$OS.$F4{ext}".format(
                root=hou.text.expandString(self.staging_dir),
                ext=self.ext
            )

        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = ["ar_ass_export_enable", "productType", "id"]
        self.lock_parameters(instance_node, to_lock)

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
