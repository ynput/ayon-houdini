import os
import hou
import json
import pyblish.api

from ayon_houdini.api import plugin


def getparms(node):

    parameters = node.parms()
    parameters += node.spareParms()
    param_data = {}

    for param in parameters:
        if param.parmTemplate().type().name() == 'FolderSet':
            continue

        # Add parameter data to the dictionary
        # FIXME: I also evaluate expressions.
        param_data[param.name()] = param.eval()   
        
    return param_data


class ExtractNodePreset(plugin.HoudiniExtractorPlugin):
    """Node Preset Extractor for any node."""
    label = "Extract Node Preset"
    order = pyblish.api.ExtractorOrder

    families = ["node_preset"]
    targets = ["local", "remote"]

    def process(self, instance: pyblish.api.Instance):
        if instance.data.get("farm"):
            self.log.debug("Should be processed on farm, skipping.")
            return

        instance_node = hou.node(instance.data["instance_node"])

        source_node = instance_node.parm("source_node").evalAsNode()
        json_path = instance_node.evalParm("filepath")

        param_data = getparms(source_node)
        node_preset = {
            "metadata":{
                "type": source_node.type().name() 
            },
            "param_data": param_data
        }
        with open(json_path, "w+") as f:
            json.dump(node_preset, fp=f, indent=2, sort_keys=True)

        representation = {
            "name": "json",
            "ext": "json",
            "files": os.path.basename(json_path),
            "stagingDir": os.path.dirname(json_path),
        }

        instance.data.setdefault("representations", []).append(representation)
