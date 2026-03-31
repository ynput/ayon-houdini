import os

import hou

from ayon_houdini.api import (
    pipeline,
    plugin,
    lib
)


class AbcArchiveLoader(plugin.HoudiniLoader):
    """Load Alembic as full geometry network hierarchy """

    product_types = {"model", "animation", "pointcache", "gpuCache"}
    label = "Load Alembic as Archive"
    representations = {"*"}
    extensions = {"abc"}
    order = -5
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        # Format file name, Houdini only wants forward slashes
        file_path = self.filepath_from_context(context)
        file_path = os.path.normpath(file_path)
        file_path = file_path.replace("\\", "/")

        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create an Alembic archive node
        node = obj.createNode("alembicarchive", node_name=node_name)
        node.moveToGoodPosition()

        # TODO: add FPS of project / folder
        node.setParms({"fileName": file_path,
                       "channelRef": True})

        # Apply some magic
        node.parm("buildHierarchy").pressButton()
        node.moveToGoodPosition()

        nodes = [node]

        self[:] = nodes

        return pipeline.containerise(node_name,
                                     namespace,
                                     nodes,
                                     context,
                                     self.__class__.__name__,
                                     suffix="")

    def update(self, container, context):
        node = container["node"]

        # Update the file path
        file_path = self.filepath_from_context(context)
        file_path = file_path.replace("\\", "/")

        # Update attributes
        node.setParms({"fileName": file_path,
                       "representation": context["representation"]["id"]})

        # Rebuild
        node.parm("buildHierarchy").pressButton()

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
            category=hou.objNodeTypeCategory(),
            default="/obj"
        )
        node = network.createNode("null", node_name=node_name)
        node.moveToGoodPosition()
        return node
