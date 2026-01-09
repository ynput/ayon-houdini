import os
import hou

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_houdini.api import (
    pipeline,
    plugin,
    lib
)

COPNET_NAME = "COPNET"


def get_image_ayon_container():
    """The Copernicus node must be in a Copernicus network.

    So we maintain a single entry point within AYON_CONTAINERS,
    just for ease of use.

    """
    root_container = pipeline.get_or_create_ayon_container()
    image_container = root_container.node(COPNET_NAME)
    if not image_container:
        image_container = root_container.createNode(
            "copnet", node_name=COPNET_NAME
        )
        image_container.moveToGoodPosition()

    return image_container


class ImageCopernicusLoader(plugin.HoudiniLoader):
    """Load images into Copernicus network.

    We prefer to create the node inside the 'active' Copernicus network
    because Copernicus does not seem to have the equivalent of an
    "Object Merge" COP node, so we cannot merge nodes from another Cop network.
    """

    product_types = {
        "imagesequence",
        "review",
        "render",
        "plate",
        "image",
        "online",
    }
    label = "Load Image (Copernicus)"
    representations = {"*"}
    order = -10

    icon = "code-fork"
    color = "orange"

    @classmethod
    def apply_settings(cls, project_settings):
        # Copernicus was introduced in Houdini 20.5.
        if hou.applicationVersion() < (20, 5, 0):
            cls.enabled = False
            return None
        return super().apply_settings(project_settings)

    def load(self, context, name=None, namespace=None, data=None):
        # Format file name, Houdini only wants forward slashes
        path = self.filepath_from_context(context)
        path = self.format_path(path, representation=context["representation"])

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create node in the active COP network
        network = lib.find_active_network(
            category=hou.copNodeTypeCategory(),
            default=None
        )
        if network is None:
            # If no active network, use a COP network
            network = get_image_ayon_container()

        node = network.createNode("file", node_name=node_name)
        node.moveToGoodPosition()

        node.setParms({
            "filename": path,
            # Add the default "C" file AOV
            "aovs": 1,
            "aov1": "C",
        })

        # Imprint it manually
        data = {
            "schema": "ayon:container-3.0",
            "id": AYON_CONTAINER_ID,
            "name": node_name,
            "namespace": namespace,
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["id"],
        }

        lib.imprint(node, data, folder="AYON")

        return node

    def update(self, container, context):
        repre_entity = context["representation"]
        node = container["node"]

        # Update the file path
        file_path = self.filepath_from_context(context)
        file_path = self.format_path(file_path, repre_entity)

        parms = {
            "filename": file_path,
            "representation": repre_entity["id"],
        }

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

        if parent.path() == f"{pipeline.AYON_CONTAINERS}/{COPNET_NAME}":
            parent.destroy()

    @staticmethod
    def format_path(path, representation):
        """Format file path correctly for single image or sequence."""

        # The path is either a single file or sequence in a folder.
        is_sequence = bool(representation["context"].get("frame"))
        if is_sequence:
            path = ImageCopernicusLoader.replace_with_frame_token(path)

        path = os.path.normpath(path)
        path = path.replace("\\", "/")
        return path

    def switch(self, container, representation):
        self.update(container, representation)

    def create_load_placeholder_node(
        self, node_name: str, placeholder_data: dict
    ) -> hou.Node:
        """Define how to create a placeholder node for this loader for the
        Workfile Template Builder system."""
        # Create node
        network = lib.find_active_network(
            category=hou.copNodeTypeCategory(),
            default="/img/copnet1"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node

