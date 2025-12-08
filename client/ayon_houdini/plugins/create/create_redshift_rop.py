# -*- coding: utf-8 -*-
"""Creator plugin to create Redshift ROP."""
import hou  # noqa

from ayon_core.pipeline import CreatorError
from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef, BoolDef


class CreateRedshiftROP(plugin.RenderLegacyProductTypeCreator):
    """Redshift ROP"""

    identifier = "io.openpype.creators.houdini.redshift_rop"
    label = "Redshift ROP"
    description = "Create Redshift ROP for rendering with Redshift"
    legacy_product_type = "redshift_rop"
    icon = "magic"
    ext = "exr"
    multi_layered_mode = "1"  # No Multi-Layered EXR File

    # Default render target
    render_target = "farm_split"

    def create(self, product_name, instance_data, pre_create_data):
        # Transfer settings from pre create to instance
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        for key in ["render_target", "review"]:
            if key in pre_create_data:
                creator_attributes[key] = pre_create_data[key]

        instance_data.update({"node_type": "Redshift_ROP"})

        instance = super(CreateRedshiftROP, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        basename = instance_node.name()

        # Also create the linked Redshift IPR Rop
        try:
            ipr_rop = instance_node.parent().createNode(
                "Redshift_IPR", node_name=f"{basename}_IPR"
            )
        except hou.OperationFailed as e:
            raise CreatorError(
                (
                    "Cannot create Redshift node. Is Redshift "
                    "installed and enabled?"
                )
            ) from e

        # Move it to directly under the Redshift ROP
        ipr_rop.setPosition(instance_node.position() + hou.Vector2(0, -1))

        # Set the linked rop to the Redshift ROP
        ipr_rop.parm("linked_rop").set(instance_node.path())
        ext: int = pre_create_data.get("image_format", 0)
        multi_layered_mode: str = pre_create_data.get(
            "multi_layered_mode", "1")

        ext_format_index = {"exr": 0, "tif": 1, "jpg": 2, "png": 3}

        if multi_layered_mode == "1":
            multipart = False
        elif multi_layered_mode == "2":
            multipart = True
        else:
            raise ValueError(
                f"Unknown value for 'multi_layered_mode': {multi_layered_mode}"
            )

        parms = {
            # Render frame range
            "trange": 1,
            # Redshift ROP settings
            "RS_outputBeautyAOVSuffix": "beauty",
            "RS_outputFileFormat": ext_format_index[ext],
        }

        if ext == "exr":
            parms["RS_outputMultilayerMode"] = multi_layered_mode
            parms["RS_aovMultipart"] = multipart

        if self.selected_nodes:
            # set up the render camera from the selected node
            camera = None
            for node in self.selected_nodes:
                if node.type().name() == "cam":
                    camera = node.path()
            parms["RS_renderCamera"] = camera or ""

        if pre_create_data.get("render_target") in {
            "farm_split",
            "local_export_farm_render",
        }:
            parms["RS_archive_enable"] = 1

        instance_node.setParms(parms)

        # Lock some AYON attributes
        to_lock = ["productType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def set_node_staging_dir(
            self, node, staging_dir, instance, pre_create_data):
        node.setParms({
            "RS_outputFileNamePrefix":
                f"{staging_dir}"
                f"/$OS.$AOV.$F4.{pre_create_data['image_format']}",
            "RS_archive_file": f"{staging_dir}/rs/$OS.$F4.rs"
        })

    def remove_instances(self, instances):
        for instance in instances:
            node = instance.data.get("instance_node")

            ipr_node = hou.node(f"{node}_IPR")
            if ipr_node:
                ipr_node.destroy()

        return super(CreateRedshiftROP, self).remove_instances(instances)

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
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):

        image_format_enum = [
            "exr", "tif", "jpg", "png",
        ]

        multi_layered_mode = [
            {"value": "1", "label": "No Multi-Layered EXR File"},
            {"value": "2", "label": "Full Multi-Layered EXR File"},
        ]

        attrs = super(CreateRedshiftROP, self).get_pre_create_attr_defs()
        attrs += [
            EnumDef("image_format",
                    image_format_enum,
                    default=self.ext,
                    label="Image Format Options"),
            EnumDef("multi_layered_mode",
                    multi_layered_mode,
                    default=self.multi_layered_mode,
                    label="Multi-Layered EXR"),
        ]
        return attrs + self.get_instance_attr_defs()

    def get_publish_families(self):
        return ["render", "redshift_rop"]
