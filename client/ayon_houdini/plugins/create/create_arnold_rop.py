from ayon_houdini.api import plugin
from ayon_houdini.api.lib import get_custom_staging_dir

from ayon_core.lib import EnumDef, BoolDef


class CreateArnoldRop(plugin.HoudiniCreator):
    """Arnold ROP"""

    identifier = "io.openpype.creators.houdini.arnold_rop"
    label = "Arnold ROP"
    product_type = "arnold_rop"
    icon = "magic"

    # Default extension
    ext = "exr"

    # Default render target
    render_target = "farm_split"

    def create(self, product_name, instance_data, pre_create_data):
        import hou
        # Transfer settings from pre create to instance
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        for key in ["render_target", "review"]:
            if key in pre_create_data:
                creator_attributes[key] = pre_create_data[key]

        # Remove the active, we are checking the bypass flag of the nodes
        instance_data.update({"node_type": "arnold"})

        instance = super(CreateArnoldRop, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        parms = {
            # Render frame range
            "trange": 1,
            # Arnold ROP settings            
            "ar_exr_half_precision": 1           # half precision
        }

        if self.enable_staging_dir:
            # keep dynamic link to product name in file path.
            self.staging_dir = get_custom_staging_dir("render", product_name) or self.staging_dir
            
            parms["ar_picture"] = "{root}/`chs('AYON_productName')`/$OS.$F4.{ext}".format(
                root=hou.text.expandString(self.staging_dir),
                ext=pre_create_data.get("image_format")
            )

            parms["ar_ass_file"] = "{root}/`chs('AYON_productName')`/ass/$OS.$F4.ass".format(
                root=hou.text.expandString(self.staging_dir)
            )

        if pre_create_data.get("render_target") == "farm_split":
            parms["ar_ass_export_enable"] = 1
                
        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = ["productType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def get_instance_attr_defs(self):
        """get instance attribute definitions.

        Attributes defined in this method are exposed in
            publish tab in the publisher UI.
        """

        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
            "farm_split": "Farm Rendering - Split export & render jobs",
        }

        return [
            BoolDef("review",
                    label="Review",
                    tooltip="Mark as reviewable",
                    default=True),
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target),
        ]

    def get_pre_create_attr_defs(self):
        image_format_enum = [
            "bmp", "cin", "exr", "jpg", "pic", "pic.gz", "png",
            "rad", "rat", "rta", "sgi", "tga", "tif",
        ]

        attrs = [
            EnumDef("image_format",
                    image_format_enum,
                    default=self.ext,
                    label="Image Format Options"),
        ]
        return attrs + self.get_instance_attr_defs()
