from ayon_core.pipeline import load
from ayon_houdini.api.pipeline import get_or_create_avalon_container


class GenericLoader(load.LoaderPlugin):
    """Load reference/payload into Solaris using AYON `lop_import` LOP"""

    product_types = {"*"}
    label = "Generic Loader"
    representations = ["*"]
    order = 9
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create node
        parent_node = get_or_create_avalon_container()
        node = parent_node.createNode("ayon::generic_loader", node_name=node_name)
        node.moveToGoodPosition()

        # Set representation id
        parm = node.parm("representation")
        parm.set(context["representation"]["id"])
        parm.pressButton()  # trigger callbacks

        nodes = [node]
        self[:] = nodes
        return node

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
