from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef, BoolDef


class CreateArnoldRop(plugin.RenderLegacyProductTypeCreator):
    """Arnold ROP"""

    identifier = "io.openpype.creators.houdini.arnold_rop"
    label = "Arnold ROP"
    product_base_type = "render"
    product_type = product_base_type
    icon = "magic"
    description =  "Create Arnold ROP for rendering with Arnold"

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

        if pre_create_data.get("render_target") in {
            "farm_split",
            "local_export_farm_render",
        }:
            parms["ar_ass_export_enable"] = 1

        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = ["productType", "productBaseType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def set_node_staging_dir(
            self, node, staging_dir, instance, pre_create_data):
        node.setParms({
            "ar_picture": f"{staging_dir}"
                          f"/$OS.$F4.{pre_create_data['image_format']}",
            "ar_ass_file": f"{staging_dir}/ass/$OS.$F4.ass"
        })

    def get_instance_attr_defs(self):
        """get instance attribute definitions.

        Attributes defined in this method are exposed in
            publish tab in the publisher UI.
        """

        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
            "farm_split": "Farm Export & Farm Rendering",
            "local_export_farm_render": "Local Export & Farm Rendering",
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

    def get_publish_families(self):
        return ["render", "arnold_rop"]
