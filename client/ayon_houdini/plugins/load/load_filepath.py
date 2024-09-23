import os
import re
import hou

from ayon_core.pipeline import Anatomy
from ayon_core.lib import StringTemplate
from ayon_houdini.api import (
    pipeline,
    plugin
)


def remove_format_spec(template: str, key: str) -> str:
    """Remove format specifier from a format token in formatting string.

    For example, change `{frame:0>4d}` into `{frame}`

    Examples:
        >>> remove_format_spec("{frame:0>4d}", "frame")
        '{frame}'
        >>> remove_format_spec("{digit:04d}/{frame:0>4d}", "frame")
        '{digit:04d}/{udim}_{frame}'
        >>> remove_format_spec("{a: >4}/{aa: >4}", "a")
        '{a}/{aa: >4}'

    """
    # Find all {key:foobar} and remove the `:foobar`
    # Pattern will be like `({key):[^}]+(})` where we use the captured groups
    # to keep those parts in the resulting string
    pattern = f"({{{key}):[^}}]+(}})"
    return re.sub(pattern, r"\1\2", template)


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
        filepath = self.filepath_from_context(context)
        parm_template_group = container.parmTemplateGroup()
        attr_folder = hou.FolderParmTemplate("attributes_folder", "Attributes")
        parm = hou.StringParmTemplate(name="filepath",
                                      label="Filepath",
                                      num_components=1,
                                      default_value=(filepath,))
        attr_folder.addParmTemplate(parm)
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
        filepath = self.filepath_from_context(context)

        node = container["node"]
        node.setParms({
            "filepath": filepath,
            "representation": str(representation_entity["id"])
        })

        # Update the parameter default value (cosmetics)
        parm_template_group = node.parmTemplateGroup()
        parm = parm_template_group.find("filepath")
        parm.setDefaultValue((filepath,))
        parm_template_group.replace(parm_template_group.find("filepath"),
                                    parm)
        node.setParmTemplateGroup(parm_template_group)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):

        node = container["node"]
        node.destroy()

    def filepath_from_context(self, context: dict) -> str:
        """Format file path for sequence with $F or <UDIM>."""
        # The path is either a single file or sequence in a folder.
        # Format frame as $F and udim as <UDIM>
        representation = context["representation"]
        frame = representation["context"].get("frame")
        udim = representation["context"].get("udim")
        if frame is not None or udim is not None:
            template: str = representation["attrib"]["template"]
            repre_context: dict = representation["context"]
            if udim is not None:
                repre_context["udim"] = "<UDIM>"
                template = remove_format_spec(template, "udim")
            if frame is not None:
                # Substitute frame number in sequence with $F with padding
                repre_context["frame"] = "$F{}".format(len(frame))   # e.g. $F4
                template = remove_format_spec(template, "frame")

            project_name: str = repre_context["project"]["name"]
            anatomy = Anatomy(project_name, project_entity=context["project"])
            repre_context["root"] = anatomy.roots
            path = StringTemplate(template).format(repre_context)
        else:
            path = super().filepath_from_context(context)

        return os.path.normpath(path).replace("\\", "/")
