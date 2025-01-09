# -*- coding: utf-8 -*-
"""Creator plugin for creating publishable Houdini Digital Assets."""
import hou

import ayon_api
from ayon_core.pipeline import (
    CreatorError,
    get_current_project_name
)
from ayon_core.lib import (
    get_ayon_username,
    BoolDef
)

from ayon_houdini.api import plugin
from ayon_houdini.api.lib import get_custom_staging_dir


# region assettools
# logic based on Houdini 19.5.752 `assettools.py` because
# this logic was removed in Houdini 20+
def get_tool_submenus(hda_def):
    """Returns the tab submenu entries of this node.

     Note: A node could be placed in multiple entries at once.

    Arguments:
        hda_def: the HDA Definition by hou.node.type().definition()

    Returns:
        Optional[list[str]]: A list of submenus
    """

    import xml.etree.ElementTree as ET
    if hda_def.hasSection('Tools.shelf'):
        sections = hda_def.sections()
        ts_section = sections['Tools.shelf'].contents()
        try:
            root = ET.fromstring(ts_section)
        except ET.ParseError:
            return None
        tool = root[0]
        submenus = tool.findall('toolSubmenu')
        if submenus:
            tool_submenus = []
            for submenu in submenus:
                if submenu is not None:
                    text = submenu.text
                    if text:
                        tool_submenus.append(submenu.text)
            if tool_submenus:
                return tool_submenus
            else:
                return None
        else:
            return None
    else:
        return None


def set_tool_submenu(hda_def,
                     new_submenu='Digital Assets'):
    """Sets the tab menu entry for a node.

    Arguments:
        hda_def: the HDA Definition by hou.node.type().definition()
        new_submenu (Optional[str]): This will be the new submenu, replacing
            old_submenu entry
    """

    context_dict = {
        'Shop': 'SHOP',
        'Cop2': 'COP2',
        'Object': 'OBJ',
        'Chop': 'CHOP',
        'Sop': 'SOP',
        'Vop': 'VOP',
        'VopNet': 'VOPNET',
        'Driver': 'ROP',
        'TOP': 'TOP',
        'Top': 'TOP',
        'Lop': 'LOP',
        'Dop': 'DOP'}

    utils_dict = {
        'Shop': 'shoptoolutils',
        'Cop2': 'cop2toolutils',
        'Object': 'objecttoolutils',
        'Chop': 'choptoolutils',
        'Sop': 'soptoolutils',
        'Vop': 'voptoolutils',
        'VopNet': 'vopnettoolutils',
        'Driver': 'drivertoolutils',
        'TOP': 'toptoolutils',
        'Top': 'toptoolutils',
        'Lop': 'loptoolutils',
        'Dop': 'doptoolutils'}

    if hda_def.hasSection('Tools.shelf'):
        old_submenu = get_tool_submenus(hda_def)[0]
    else:
        # Add default tools shelf section
        content = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
<!-- This file contains definitions of shelves, toolbars, and tools.
It should not be hand-edited when it is being used by the application.
Note, that two definitions of the same element are not allowed in
a single file. -->
<tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
<toolMenuContext name="viewer">
<contextNetType>SOP</contextNetType>
</toolMenuContext>
<toolMenuContext name="network">
<contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
</toolMenuContext>
<toolSubmenu>Digital Assets</toolSubmenu>
<script scriptType="python"><![CDATA[import soptoolutils
soptoolutils.genericTool(kwargs, \'$HDA_NAME\')]]></script>
</tool>
</shelfDocument>
        """
        
        nodetype_category_name = hda_def.nodeType().category().name()
        context = context_dict[nodetype_category_name]
        util = utils_dict[nodetype_category_name]
        content = content.replace(
            "<contextNetType>SOP</contextNetType>",
            f"<contextNetType>{context}</contextNetType>")
        content = content.replace('soptoolutils', util)
        hda_def.addSection('Tools.shelf', content)
        old_submenu = 'Digital Assets'

    # Replace submenu
    tools = hda_def.sections()["Tools.shelf"]
    content = tools.contents()
    content = content.replace(
        f"<toolSubmenu>{old_submenu}</toolSubmenu>",
        f"<toolSubmenu>{new_submenu}</toolSubmenu>"
    )

    hda_def.addSection('Tools.shelf', content)
# endregion


def promote_spare_parameters(node):
    """Promote spare parameters to HDA node type definition"""
    ptg = node.parmTemplateGroup()
    node.type().definition().setParmTemplateGroup(ptg)


class CreateHDA(plugin.HoudiniCreator):
    """Publish Houdini Digital Asset file."""

    identifier = "io.openpype.creators.houdini.hda"
    label = "Houdini Digital Asset (Hda)"
    product_type = "hda"
    icon = "gears"
    maintain_selection = False

    def _check_existing(self, folder_path, product_name):
        # type: (str, str) -> bool
        """Check if existing product name versions already exists."""
        # Get all products of the current folder
        project_name = self.project_name
        folder_entity = ayon_api.get_folder_by_path(
            project_name, folder_path, fields={"id"}
        )
        product_entities = ayon_api.get_products(
            project_name, folder_ids={folder_entity["id"]}, fields={"name"}
        )
        existing_product_names_low = {
            product_entity["name"].lower()
            for product_entity in product_entities
        }
        return product_name.lower() in existing_product_names_low

    def create_instance_node(
        self,
        folder_path,
        node_name,
        parent,
        node_type="geometry",
        pre_create_data=None
    ):
        if pre_create_data is None:
            pre_create_data = {}

        use_promote_spare_parameters = pre_create_data.get(
            "use_promote_spare_parameters", True)

        if self.selected_nodes:
            # if we have `use selection` enabled, and we have some
            # selected nodes ...
            one_node_selected = len(self.selected_nodes) == 1
            first_selected_node = self.selected_nodes[0]

            # If only an HDA is selected, publish just that node as HDA.
            if one_node_selected and first_selected_node.type().definition():
                to_hda = first_selected_node
                use_promote_spare_parameters = False

            # If only a single subnet is selected, turn that into the HDA.
            elif one_node_selected and first_selected_node.type().name() == "subnet":
                to_hda = first_selected_node
                to_hda.setName("{}_subnet".format(node_name), unique_name=True)

            # Collapse all selected nodes into a subnet and turn that into
            # the HDA.
            else:
                parent_node = self.selected_nodes[0].parent()
                subnet = parent_node.collapseIntoSubnet(
                    self.selected_nodes,
                    subnet_name="{}_subnet".format(node_name))
                subnet.moveToGoodPosition()
                to_hda = subnet
        else:
            # Use Obj as the default path
            parent_node = hou.node("/obj")
            # Find and return the NetworkEditor pane tab with the minimum index
            pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
            if isinstance(pane, hou.NetworkEditor):
                # Use the NetworkEditor pane path as the parent path.
                parent_node = pane.pwd()

            to_hda = parent_node.createNode(
                "subnet", node_name="{}_subnet".format(node_name))

        if not to_hda.type().definition():
            # if node type has not its definition, it is not user
            # created hda. We test if hda can be created from the node.
            if not to_hda.canCreateDigitalAsset():
                raise CreatorError(
                    "cannot create hda from node {}".format(to_hda))

            # Pick a unique type name for HDA product per folder path per project.
            type_name = (
                "{project_name}{folder_path}_{node_name}".format(
                    project_name=get_current_project_name(),
                    folder_path=folder_path.replace("/","_"),
                    node_name=node_name
                )
            )

            hda_file_name = None
            if self.enable_staging_path_management:
                self.staging_dir = get_custom_staging_dir(self.product_type, node_name) or self.staging_dir
                hda_file_name = "{}/HDAs/{}.hda".format(self.staging_dir, node_name)

            hda_node = to_hda.createDigitalAsset(
                name=type_name,
                description=node_name,
                hda_file_name=hda_file_name,
                ignore_external_references=True,
                min_num_inputs=0,
                max_num_inputs=len(to_hda.inputs()) or 1,
            )

            if use_promote_spare_parameters:
                # Similar to Houdini default behavior, when enabled this will
                # promote spare parameters to type properties on initial
                # creation of the HDA.
                promote_spare_parameters(hda_node)

            hda_node.layoutChildren()
        elif self._check_existing(folder_path, node_name):
            raise CreatorError(
                ("product {} is already published with different HDA"
                 "definition.").format(node_name))
        else:
            hda_node = to_hda

        # If user tries to create the same HDA instance more than
        # once, then all of them will have the same product name and
        # point to the same hda_file_name. But, their node names will
        # be incremented.
        hda_node.setName(node_name, unique_name=True)
        self.customize_node_look(hda_node)

        # Set Custom settings.
        hda_def = hda_node.type().definition()

        if pre_create_data.get("set_user"):
            hda_def.setUserInfo(get_ayon_username())

        if pre_create_data.get("use_project"):
            set_tool_submenu(hda_def, "AYON/{}".format(self.project_name))

        return hda_node

    def get_network_categories(self):
        # Houdini allows creating sub-network nodes inside
        # these categories.
        # Therefore this plugin can work in these categories.
        return [
            hou.chopNodeTypeCategory(),
            hou.cop2NodeTypeCategory(),
            hou.dopNodeTypeCategory(),
            hou.ropNodeTypeCategory(),
            hou.lopNodeTypeCategory(),
            hou.objNodeTypeCategory(),
            hou.sopNodeTypeCategory(),
            hou.topNodeTypeCategory(),
            hou.vopNodeTypeCategory()
        ]

    def get_pre_create_attr_defs(self):
        attrs = super(CreateHDA, self).get_pre_create_attr_defs()
        return attrs + [
            BoolDef("set_user",
                    tooltip="Set current user as the author of the HDA",
                    default=False,
                    label="Set Current User"),
            BoolDef("use_project",
                    tooltip="Use project name as tab submenu path.\n"
                            "The location in TAB Menu will be\n"
                            "'AYON/project_name/your_HDA_name'",
                    default=True,
                    label="Use Project as menu entry"),
            BoolDef("use_promote_spare_parameters",
                    tooltip="Similar to Houdini default behavior, when "
                            "enabled this will promote spare parameters to "
                            "type properties on initial creation of the HDA.",
                    default=True,
                    label="Promote Spare Parameters"),
        ]

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
        Pass product name from product name templates as dynamic data.
        """
        dynamic_data = super(CreateHDA, self).get_dynamic_data(
            project_name,
            folder_entity,
            task_entity,
            variant,
            host_name,
            instance
        )

        dynamic_data.update(
            {
                "asset": folder_entity["name"],
                "folder": {
                            "label": folder_entity["label"],
                            "name": folder_entity["name"]
                }
            }
        )

        return dynamic_data
