# -*- coding: utf-8 -*-
"""Creator plugin for creating houdini node presets."""
from ayon_houdini.api import plugin
import hou


def _update_node_parmtemplate(node, defaults):
    """update node parm template.

    It adds a new folder parm that includes 
    filepath and operator node selector.
    """
    parm_group = node.parmTemplateGroup()

    # Hide unnecessary parameters
    for parm in {"execute", "renderdialog"}:
        p = parm_group.find(parm)
        p.hide(True)
        parm_group.replace(parm, p)

    # Create essential parameters
    folder_template = hou.FolderParmTemplate(
        name="main",
        label="Main",
        folder_type=hou.folderType.Tabs
    )

    filepath_template = hou.StringParmTemplate(
        name="filepath",
        label="Preset File",
        num_components=1,
        default_value=(defaults.get("filepath", ""),),
        string_type=hou.stringParmType.FileReference,
        tags= { 
            "filechooser_pattern" : "*.json", 
        }
    )

    operatore_template = hou.StringParmTemplate(
        name="source_node",
        label="Source Node",
        num_components=1,
        default_value=(defaults.get("source_node", ""),),
        string_type=hou.stringParmType.NodeReference,
        tags= { 
            "oprelative" : "."
        }
    )

    folder_template.addParmTemplate(filepath_template)
    folder_template.addParmTemplate(operatore_template)
    
    # TODO: make the Main and Extra Tab next to each other.
    parm_group.insertBefore((0,), folder_template)

    node.setParmTemplateGroup(parm_group) 


class CreateNodePreset(plugin.HoudiniCreator):
    """NodePreset creator.
    
    Node Presets capture the parameters of the source node.
    """
    identifier = "io.ayon.creators.houdini.node_preset"
    label = "Node Preset"
    product_type = "node_preset"
    icon = "gears"

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "null"})

        instance = super(CreateNodePreset, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))
        

        filepath = "{}{}".format(
            hou.text.expandString("$HIP/pyblish/"),
            f"{product_name}.json"
        )
        source_node = ""
        
        if self.selected_nodes:
            source_node = self.selected_nodes[0].path()

        defaults= {
            "filepath": filepath, 
            "source_node": source_node
        }
        _update_node_parmtemplate(instance_node, defaults)


    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()

        return attrs + self.get_instance_attr_defs()

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory()
        ]
