import hou

from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
)
from ayon_houdini.api import (
    plugin,
    lib
)


class USDReferenceLoader(plugin.HoudiniLoader):
    """Reference USD file in Solaris"""

    product_types = {
        "usd",
        "usdCamera",
    }
    label = "Reference USD"
    representations = {"usd", "usda", "usdlc", "usdnc", "abc"}
    order = -8

    icon = "code-fork"
    color = "orange"

    use_ayon_entity_uri = False

    def load(self, context, name=None, namespace=None, data=None):

        # Format file name, Houdini only wants forward slashes
        file_path = self.filepath_from_context(context)
        file_path = file_path.replace("\\", "/")

        # Get the root node
        stage = hou.node("/stage")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create USD reference
        container = stage.createNode("reference", node_name=node_name)
        container.setParms({"filepath1": file_path})
        container.moveToGoodPosition()

        # Imprint it manually
        data = {
            "schema": "ayon:container-3.0",
            "id": AYON_CONTAINER_ID,
            "name": node_name,
            "namespace": namespace,
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["id"],
        }

        # todo: add folder="AYON"
        lib.imprint(container, data)

        return container

    def update(self, container, context):
        node = container["node"]

        # Update the file path
        file_path = self.filepath_from_context(context)
        file_path = file_path.replace("\\", "/")

        # Update attributes
        node.setParms(
            {
                "filepath1": file_path,
                "representation": context["representation"]["id"],
            }
        )

        # Reload files
        node.parm("reload").pressButton()

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
            category=hou.lopNodeTypeCategory(),
            default="/stage"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node

