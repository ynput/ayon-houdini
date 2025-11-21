from ayon_core.pipeline import load
from ayon_houdini.api.lib import find_active_network
from ayon_houdini.api import hda_utils

import hou


class LOPLoadShotLoader(load.LoaderPlugin):
    """Load sublayer into Solaris using AYON Load Shot LOP"""

    product_types = {"*"}
    label = "Load Shot (LOPs)"
    representations = ["usd", "abc", "usda", "usdc"]
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create node
        network = find_active_network(
            category=hou.lopNodeTypeCategory(),
            default="/stage"
        )
        node = network.createNode("ayon::load_shot", node_name=node_name)
        node.moveToGoodPosition()

        hda_utils.set_node_representation_from_context(node, context)

        nodes = [node]
        self[:] = nodes

        return node

    def update(self, container, context):
        node = container["node"]
        hda_utils.set_node_representation_from_context(node, context)

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
        network = find_active_network(
            category=hou.lopNodeTypeCategory(),
            default="/stage"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node

