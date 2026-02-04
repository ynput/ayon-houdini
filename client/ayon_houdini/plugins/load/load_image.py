import hou

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_houdini.api import (
    pipeline,
    plugin,
    lib
)


def get_image_ayon_container():
    """The COP2 files must be in a COP2 network.

    So we maintain a single entry point within AYON_CONTAINERS,
    just for ease of use.

    """
    root_container = pipeline.get_or_create_ayon_container()
    image_container = root_container.node("IMAGES")
    if not image_container:
        image_container = root_container.createNode(
            "cop2net", node_name="IMAGES"
        )
        image_container.moveToGoodPosition()

    return image_container


class ImageLoader(plugin.HoudiniLoader):
    """Load images into COP2"""

    product_types = {
        "imagesequence",
        "review",
        "render",
        "plate",
        "image",
        "online",
    }
    label = "Load Image (COP2)"
    representations = {"*"}
    order = -9

    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        # Get the root node
        parent = get_image_ayon_container()

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        node = parent.createNode("file", node_name=node_name)
        node.moveToGoodPosition()

        parms = {"filename1": self.format_path(context)}
        parms.update(self.get_colorspace_parms(context["representation"]))

        node.setParms(parms)

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
        lib.imprint(node, data)

        return node

    def update(self, container, context):
        repre_entity = context["representation"]
        node = container["node"]

        # Update the file path
        parms = {
            "filename1": self.format_path(context),
            "representation": repre_entity["id"],
        }

        parms.update(self.get_colorspace_parms(repre_entity))

        # Update attributes
        node.setParms(parms)

    def remove(self, container):
        node = container["node"]

        # Let's clean up the IMAGES COP2 network
        # if it ends up being empty and we deleted
        # the last file node. Store the parent
        # before we delete the node.
        parent = node.parent()

        node.destroy()

        if not parent.children():
            parent.destroy()

    def get_colorspace_parms(self, representation: dict) -> dict:
        """Return the color space parameters.

        Returns the values for the colorspace parameters on the node if there
        is colorspace data on the representation.

        Arguments:
            representation (dict): The representation entity.

        Returns:
            dict: Parm to value mapping if colorspace data is defined.

        """
        # Using OCIO colorspace on COP2 File node is only supported in Hou 20+
        major, _, _ = hou.applicationVersion()
        if major < 20:
            return {}

        data = representation.get("data", {}).get("colorspaceData", {})
        if not data:
            return {}

        colorspace = data["colorspace"]
        if colorspace:
            return {
                "colorspace": 3,  # Use OpenColorIO
                "ocio_space": colorspace
            }

        return {}

    def switch(self, container, representation):
        self.update(container, representation)

    def create_load_placeholder_node(
        self, node_name: str, placeholder_data: dict
    ) -> hou.Node:
        """Define how to create a placeholder node for this loader for the
        Workfile Template Builder system."""
        # Create node
        network = lib.find_active_network(
            category=hou.cop2NodeTypeCategory(),
            default="/img/copnet1"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node
