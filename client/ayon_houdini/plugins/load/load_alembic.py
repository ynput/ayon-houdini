import os

import hou

from ayon_houdini.api import (
    pipeline,
    plugin,
    lib
)


class AbcLoader(plugin.HoudiniLoader):
    """Load Alembic"""

    product_types = {"model", "animation", "pointcache", "gpuCache"}
    label = "Load Alembic"
    representations = {"*"}
    extensions = {"abc"}
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        file_path = self.filepath_from_context(context)

        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create a new geo node
        container = obj.createNode("geo", node_name=node_name)

        # Remove the file node, it only loads static meshes
        # Houdini 17 has removed the file node from the geo node
        file_node = container.node("file1")
        if file_node:
            file_node.destroy()

        # Create an alembic node (supports animation)
        alembic = container.createNode("alembic", node_name=node_name)
        alembic.setParms({"fileName": file_path})

        # Position nodes nicely
        container.moveToGoodPosition()
        container.layoutChildren()

        nodes = [container, alembic]

        return pipeline.containerise(
            node_name,
            namespace,
            nodes,
            context,
            self.__class__.__name__,
            suffix="",
        )

    def update(self, container, context):
        node = container["node"]
        try:
            alembic_node = next(
                n for n in node.children() if n.type().name() == "alembic"
            )
        except StopIteration:
            self.log.error("Could not find node of type `alembic`")
            return

        # Update the file path
        file_path = self.filepath_from_context(context)

        alembic_node.setParms({"fileName": file_path})

        # Update attribute
        node.setParms({"representation": context["representation"]["id"]})

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def switch(self, container, context):
        self.update(container, context)

    @classmethod
    def filepath_from_context(cls, context):
        file_path = super().filepath_from_context(context)
        # Format file name, Houdini only wants forward slashes
        return os.path.normpath(file_path).replace("\\", "/")

    def create_load_placeholder_node(
        self, node_name: str, placeholder_data: dict
    ) -> hou.Node:
        """Define how to create a placeholder node for this loader for the
        Workfile Template Builder system."""
        # Create node
        network = lib.find_active_network(
            category=hou.sopNodeTypeCategory(),
            default="/obj/geo1"
        )
        if not network:
            network = hou.node("/obj").createNode("geo", "geo1")

        node = network.createNode("object_merge", node_name=node_name)
        node.moveToGoodPosition()
        return node