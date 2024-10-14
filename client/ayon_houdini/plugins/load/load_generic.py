from ayon_core.pipeline import load
from ayon_houdini.api.lib import find_active_network

import hou


class GenericLoader(load.LoaderPlugin):
    """Load reference/payload into Solaris using AYON `lop_import` LOP"""

    product_types = {"*"}
    label = "Generic Loader"
    representations = ["*"]
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create node
        network = find_active_network()
        node = network.createNode("ayon::generic_loader", node_name=node_name)
        node.moveToGoodPosition()

        # Set representation id
        parm = node.parm("representation")
        parm.set(context["representation"]["id"])
        parm.pressButton()  # trigger callbacks

        nodes = [node]
        self[:] = nodes

    def update(self, container, context):
        node = container["node"]

        # Set representation id
        parm = node.parm("representation")
        parm.set(context["representation"]["id"])
        parm.pressButton()  # trigger callbacks

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def switch(self, container, context):
        self.update(container, context)
