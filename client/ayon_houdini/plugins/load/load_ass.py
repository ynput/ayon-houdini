import hou

from ayon_houdini.api import (
    pipeline,
    plugin,
    lib,
)


class AssLoader(plugin.HoudiniLoader):
    """Load .ass with Arnold Procedural"""

    product_base_types = {"ass"}
    product_types = product_base_types
    label = "Load Arnold Procedural"
    representations = {"ass"}
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create a new geo node
        procedural = obj.createNode("arnold::procedural", node_name=node_name)

        procedural.setParms(
            {
                "ar_filename": self.format_path(context)
            })

        nodes = [procedural]
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
        procedural = container["node"]
        procedural.setParms({
            "ar_filename": self.format_path(context),
            "representation": context["representation"]["id"]
        })

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def switch(self, container, context):
        self.update(container, context)

    def create_load_placeholder_node(
        self, node_name: str, placeholder_data: dict
    ) -> hou.Node:
        """Define how to create a placeholder node for this loader for the
        Workfile Template Builder system."""
        # Create node
        network = lib.find_active_network(
            category=hou.sopNodeTypeCategory(),
            default="/obj"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node
