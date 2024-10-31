from ayon_houdini.api import (
    hda_utils,
    plugin
)
from ayon_houdini.api.pipeline import get_or_create_avalon_container


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

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create node
        parent_node = get_or_create_avalon_container()
        node = parent_node.createNode("ayon::generic_loader",
                                      node_name=node_name)
        node.moveToGoodPosition()

        hda_utils.set_node_representation_from_context(node, context)

    def update(self, container, context):

        # First we handle backwards compatibility where this loader still
        # loaded using a `null` node instead of the `ayon::generic_loader`
        node = container["node"]
        if node.type().name() == "null":
            # Update the legacy way
            self.update_legacy(node, context)
            return

        hda_utils.set_node_representation_from_context(node, context)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def update_legacy(self, node, context):
        # Update the file path
        representation_entity = context["representation"]
        filepath = hda_utils.get_filepath_from_context(context)

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