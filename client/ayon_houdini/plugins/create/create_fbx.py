# -*- coding: utf-8 -*-
"""Creator plugins for FBX, like static mesh and model products"""
from ayon_houdini.api import plugin
from ayon_core.lib import BoolDef, EnumDef

import hou


class CreateFBX(plugin.HoudiniCreator):
    """Model as FBX."""

    identifier = "io.ayon.creators.houdini.model.fbx"
    label = "Model (FBX)"
    product_type = "model"
    icon = "cube"
    default_variants = ["Main"]
    description = "Create a static model as FBX file"

    # Default render target
    render_target = "local"

    def get_publish_families(self):
        return ["fbx", "model", "publish.hou"]

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "filmboxfbx"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super().create(
            product_name,
            instance_data,
            pre_create_data)

        # get the created rop node
        instance_node = hou.node(instance.get("instance_node"))

        # prepare parms
        parms = {
            "startnode": self.get_selection(),
            # vertex cache format
            "vcformat": pre_create_data.get("vcformat"),
            "convertunits": pre_create_data.get("convertunits"),
            # set render range to use frame range start-end frame
            "trange": 1,
            "createsubnetroot": pre_create_data.get("createsubnetroot"),
            "exportkind": pre_create_data.get("exportkind")
        }

        # set parms
        instance_node.setParms(parms)

        # Lock any parameters in this list
        to_lock = ["productType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def set_node_staging_dir(
            self, node, staging_dir, instance, pre_create_data):
        node.parm("sopoutput").set(f"{staging_dir}/$OS.fbx")

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.objNodeTypeCategory(),
            hou.sopNodeTypeCategory()
        ]

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
        """Add settings for users. """

        attrs = super().get_pre_create_attr_defs()
        createsubnetroot = BoolDef("createsubnetroot",
                                   tooltip="Create an extra root for the "
                                           "Export node when it's a "
                                           "subnetwork. This causes the "
                                           "exporting subnetwork node to be "
                                           "represented in the FBX file.",
                                   default=False,
                                   label="Create Root for Subnet")
        vcformat = EnumDef("vcformat",
                           items={
                               0: "Maya Compatible (MC)",
                               1: "3DS MAX Compatible (PC2)"
                           },
                           default=0,
                           label="Vertex Cache Format")
        convert_units = BoolDef("convertunits",
                                tooltip="When on, the FBX is converted"
                                        "from the current Houdini "
                                        "system units to the native "
                                        "FBX unit of centimeters.",
                                default=False,
                                label="Convert Units")
        format_ascii = EnumDef("exportkind",
                               items={
                                   0: "Binary",
                                   1: "ASCII"
                               },
                               default=0,
                               label="Export Format")
        return attrs + [
            createsubnetroot,
            vcformat,
            convert_units,
            format_ascii,
        ] + self.get_instance_attr_defs()

    def get_dynamic_data(
        self,
        project_name,
        folder_entity,
        task_entity,
        variant,
        host_name,
        instance
    ):
        """
        The default product name templates for Unreal include {asset} and thus
        we should pass that along as dynamic data.
        """
        dynamic_data = super().get_dynamic_data(
            project_name,
            folder_entity,
            task_entity,
            variant,
            host_name,
            instance
        )
        dynamic_data["asset"] = folder_entity["name"]
        return dynamic_data

    def get_selection(self):
        """Selection Logic.

        how self.selected_nodes should be processed to get
        the desirable node from selection.

        Returns:
            str : node path
        """

        selection = ""

        if self.selected_nodes:
            selected_node = self.selected_nodes[0]

            # Accept sop level nodes (e.g. /obj/geo1/box1)
            if isinstance(selected_node, hou.SopNode):
                selection = selected_node.path()
                self.log.debug(
                    "Valid SopNode selection, 'Export' in filmboxfbx"
                    " will be set to '%s'.", selected_node
                )

            # Accept object level nodes (e.g. /obj/geo1)
            elif isinstance(selected_node, hou.ObjNode):
                selection = selected_node.path()
                self.log.debug(
                    "Valid ObjNode selection, 'Export' in filmboxfbx "
                    "will be set to the child path '%s'.", selection
                )

            else:
                self.log.debug(
                    "Selection isn't valid. 'Export' in "
                    "filmboxfbx will be empty."
                )
        else:
            self.log.debug(
                "No Selection. 'Export' in filmboxfbx will be empty."
            )

        return selection


class CreateStaticMesh(CreateFBX):
    """Create static meshes as FBX, usually used for Unreal Engine"""

    identifier = "io.openpype.creators.houdini.staticmesh.fbx"
    label = "Static Mesh (FBX)"
    product_type = "staticMesh"
    icon = "cube"
    description = __doc__

    def get_publish_families(self):
        return ["fbx", "staticMesh", "publish.hou"]

