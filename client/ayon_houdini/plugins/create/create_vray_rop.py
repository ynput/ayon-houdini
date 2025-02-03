# -*- coding: utf-8 -*-
"""Creator plugin to create VRay ROP."""
import hou

from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatorError
from ayon_core.lib import EnumDef, BoolDef


class CreateVrayROP(plugin.HoudiniCreator):
    """VRay ROP"""

    identifier = "io.openpype.creators.houdini.vray_rop"
    label = "VRay ROP"
    product_type = "vray_rop"
    icon = "magic"
    ext = "exr"

    # Default render target
    render_target = "farm_split"

    def create(self, product_name, instance_data, pre_create_data):
        # Transfer settings from pre create to instance
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        for key in ["render_target", "review"]:
            if key in pre_create_data:
                creator_attributes[key] = pre_create_data[key]

        instance_data.update({"node_type": "vray_renderer"})

        instance = super(CreateVrayROP, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        # Add IPR for Vray
        basename = instance_node.name()
        try:
            ipr_rop = instance_node.parent().createNode(
                "vray", node_name=basename + "_IPR"
            )
        except hou.OperationFailed:
            raise CreatorError(
                "Cannot create Vray render node. "
                "Make sure Vray installed and enabled!"
            )

        ipr_rop.setPosition(instance_node.position() + hou.Vector2(0, -1))
        ipr_rop.parm("rop").set(instance_node.path())

        parms = {
            "trange": 1,
            "SettingsEXR_bits_per_channel": "16",   # half precision
            "use_render_channels": 0,
        }

        if pre_create_data.get("render_target") == "farm_split":
            # Setting render_export_mode to "2" because that's for
            # "Export only" ("1" is for "Export & Render")
            parms["render_export_mode"] = "2"

        if self.selected_nodes:
            # set up the render camera from the selected node
            camera = None
            for node in self.selected_nodes:
                if node.type().name() == "cam":
                    camera = node.path()
            parms.update({
                "render_camera": camera or ""
            })

        # Enable render element
        instance_data["RenderElement"] = pre_create_data.get("render_element_enabled")         # noqa
        if pre_create_data.get("render_element_enabled", True):
            re_rop = instance_node.parent().createNode(
                "vray_render_channels",
                node_name=basename + "_render_element"
            )
            # move the render element node next to the vray renderer node
            re_rop.setPosition(instance_node.position() + hou.Vector2(0, 1))
            re_path = re_rop.path()
            parms.update({
                "use_render_channels": 1,
                "render_network_render_channels": re_path
            })

        custom_res = pre_create_data.get("override_resolution")
        if custom_res:
            parms.update({"override_camerares": 1})

        instance_node.setParms(parms)

        # lock parameters from AVALON
        to_lock = ["productType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def set_node_staging_dir(self, node, staging_dir, instance, pre_create_data):
        node.parm("render_export_filepath").set(f"{staging_dir}/vrscene/$OS.$F4.vrscene")
        
        if pre_create_data.get("render_element_enabled", True):
            node.parm("SettingsOutput_img_file_path").set(f"{staging_dir}/$OS.$AOV.$F4.{pre_create_data['image_format']}") 
        else:
             node.parm("SettingsOutput_img_file_path").set(f"{staging_dir}/$OS.$F4.{pre_create_data['image_format']}")


    def remove_instances(self, instances):
        for instance in instances:
            node = instance.data.get("instance_node")
            # for the extra render node from the plugins
            # such as vray and redshift
            ipr_node = hou.node("{}{}".format(node, "_IPR"))
            if ipr_node:
                ipr_node.destroy()
            re_node = hou.node("{}{}".format(node,
                                             "_render_element"))
            if re_node:
                re_node.destroy()

        return super(CreateVrayROP, self).remove_instances(instances)

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
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):
        image_format_enum = [
            "bmp", "cin", "exr", "jpg", "pic", "pic.gz", "png",
            "rad", "rat", "rta", "sgi", "tga", "tif",
        ]

        attrs = super(CreateVrayROP, self).get_pre_create_attr_defs()

        attrs += [
            EnumDef("image_format",
                    image_format_enum,
                    default=self.ext,
                    label="Image Format Options"),
            BoolDef("override_resolution",
                    label="Override Camera Resolution",
                    tooltip="Override the current camera "
                            "resolution, recommended for IPR.",
                    default=False),
            BoolDef("render_element_enabled",
                    label="Render Element",
                    tooltip="Create Render Element Node "
                            "if enabled",
                    default=False)
        ]
        return attrs + self.get_instance_attr_defs()
