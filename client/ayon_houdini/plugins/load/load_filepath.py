import os
import re
import hou

from ayon_houdini.api import (
    pipeline,
    plugin
)


class FilePathLoader(plugin.HoudiniLoader):
    """Load a managed filepath to a null node.

    This is useful if for a particular workflow there is no existing loader
    yet. A Houdini artists can load as the generic filepath loader and then
    reference the relevant Houdini parm to use the exact value. The benefit
    is that this filepath will be managed and can be updated as usual.

    """

    label = "Load filepath to node"
    order = 9
    icon = "link"
    color = "white"
    product_types = {"*"}
    representations = {"*"}

    def _add_more_node_params(self, attr_folder, node):
        # allow subclasses to add more params.
        pass

    def load(self, context, name=None, namespace=None, data=None):

        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create a null node
        container = obj.createNode("null", node_name=node_name)

        # Destroy any children
        for node in container.children():
            node.destroy()

        # Add filepath attribute, set value as default value
        filepath = self.format_path(
            path=self.filepath_from_context(context),
            representation=context["representation"]
        )
        parm_template_group = container.parmTemplateGroup()
        attr_folder = hou.FolderParmTemplate("attributes_folder", "Attributes")
        parm = hou.StringParmTemplate(name="filepath",
                                      label="Filepath",
                                      num_components=1,
                                      default_value=(filepath,))
        attr_folder.addParmTemplate(parm)

        # Call add more node params.
        self._add_more_node_params(attr_folder, container)

        parm_template_group.append(attr_folder)

        # Hide some default labels
        for folder_label in ["Transform", "Render", "Misc", "Redshift OBJ"]:
            folder = parm_template_group.findFolder(folder_label)
            if not folder:
                continue
            parm_template_group.hideFolder(folder_label, True)

        container.setParmTemplateGroup(parm_template_group)

        container.setDisplayFlag(False)
        container.setSelectableInViewport(False)
        container.useXray(False)

        nodes = [container]

        self[:] = nodes

        return pipeline.containerise(
            node_name,
            namespace,
            nodes,
            context,
            self.__class__.__name__,
            suffix="",
        )

    def update(self, container, context):

        # Update the file path
        representation_entity = context["representation"]
        file_path = self.format_path(
            path=self.filepath_from_context(context),
            representation=representation_entity
        )

        node = container["node"]
        node.setParms({
            "filepath": file_path,
            "representation": str(representation_entity["id"])
        })

        # Update the parameter default value (cosmetics)
        parm_template_group = node.parmTemplateGroup()
        parm = parm_template_group.find("filepath")
        parm.setDefaultValue((file_path,))
        parm_template_group.replace(parm_template_group.find("filepath"),
                                    parm)
        node.setParmTemplateGroup(parm_template_group)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):

        node = container["node"]
        node.destroy()

    @staticmethod
    def format_path(path: str, representation: dict) -> str:
        """Format file path for sequence with $F."""
        if not os.path.exists(path):
            raise RuntimeError("Path does not exist: %s" % path)

        # The path is either a single file or sequence in a folder.
        frame = representation["context"].get("frame")
        if frame is not None:
            # Substitute frame number in sequence with $F with padding
            ext = representation.get("ext", representation["name"])
            token = "$F{}".format(len(frame))   # e.g. $F4
            pattern = r"\.(\d+)\.{ext}$".format(ext=re.escape(ext))
            path = re.sub(pattern, ".{}.{}".format(token, ext), path)

        return os.path.normpath(path).replace("\\", "/")


class NodePresetLoader(FilePathLoader):
    """Load node presets.

    It works the same as FilePathLoader, except its extra parameters,
        2 buttons and target node field.
        Buttons are used apply the node preset to the target node.
    """

    label = "Load Node Preset"
    order = 9
    icon = "link"
    color = "white"
    product_types = {"node_preset"}
    representations = {"json"}

    # TODO: 
    #  1. Find a way to cache the node preset, instead of reading the file every time.
    #  2. Notify the user with the results of Apply button (succeeded, failed and why).
    #  Note:
    #    So far we manage the node preset, but we don't manage setting the node preset.
    def _add_more_node_params(self, attr_folder, node):
        # allow subclasses to add more params.

        operatore_template = hou.StringParmTemplate(
            name="target_node",
            label="Target Node",
            num_components=1,
            default_value=("",),
            string_type=hou.stringParmType.NodeReference,
            tags= { 
                "oprelative" : ".",
                "script_callback" : """
import json
from ayon_houdini.api.lib import load_node_preset

json_path = hou.parm("./filepath").eval()
target_node = hou.parm("./target_node").evalAsNode()
node_preset = {}
with open(json_path, "r") as f:
    node_preset = json.load(f)

node_type = node_preset["metadata"]["type"]

hou.pwd().setColor(hou.Color(0.7, 0.8, 0.87))
hou.pwd().setComment("")
hou.pwd().setGenericFlag(hou.nodeFlag.DisplayComment, True)
if target_node and target_node.type().name() != node_type:
    hou.pwd().setColor(hou.Color(0.8, 0.45, 0.1))
    hou.pwd().setComment(
        f"Target Node type '{target_node.type().name()}' doesn't match the loaded preset type '{node_type}'."
        "Please note, Applying the preset skips parameters that doesn't exist"
    )
""",
            "script_callback_language" : "python",
            }
        )

        apply_template = hou.ButtonParmTemplate(
            name="apply_preset",
            label="Apply Preset",
            tags= { 
                "script_callback" : """
import json
from ayon_houdini.api.lib import load_node_preset

json_path = hou.parm("./filepath").eval()
target_node = hou.parm("./target_node").evalAsNode()
if target_node:
    node_preset = {}
    with open(json_path, "r") as f:
        node_preset = json.load(f)

    load_node_preset(target_node, node_preset)
""",
                "script_callback_language" : "python",
            },
            help=("Apply render preset to the target node."
                  "Skip updating locked parameters.")
        )

        force_apply_template = hou.ButtonParmTemplate(
            name="force_apply_preset",
            label="Force Apply Preset",
            tags= { 
                "script_callback" : """
import json
from ayon_houdini.api.lib import load_node_preset

json_path = hou.parm("./filepath").eval()
target_node = hou.parm("./target_node").evalAsNode()
if target_node:
    node_preset = {}
    with open(json_path, "r") as f:
        node_preset = json.load(f)

    load_node_preset(target_node, node_preset, update_locked=True)
""",
                "script_callback_language" : "python",
            },
            help=("Apply render preset to the target node."
                  "Update also locked parameters.")
        )

        attr_folder.addParmTemplate(operatore_template)
        attr_folder.addParmTemplate(apply_template)
        attr_folder.addParmTemplate(force_apply_template)
