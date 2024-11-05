from ayon_core.pipeline import load
from ayon_houdini.api.lib import find_active_network
from ayon_houdini.api import hda_utils

import hou


class LOPLoadAssetLoader(load.LoaderPlugin):
    """Load reference/payload into Solaris using AYON `lop_import` LOP"""

    product_types = {"*"}
    label = "Load Asset (LOPs)"
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
        node = network.createNode("ayon::lop_import", node_name=node_name)
        node.moveToGoodPosition()

        hda_utils.set_node_representation_from_context(node, context)

        nodes = [node]
        self[:] = nodes

    def update(self, container, context):
        node = container["node"]
        hda_utils.set_node_representation_from_context(node, context)

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def switch(self, container, context):
        self.update(container, context)
