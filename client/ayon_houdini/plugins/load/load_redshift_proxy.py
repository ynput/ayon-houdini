import os
import hou

from ayon_core.pipeline.load import LoadError

from ayon_houdini.api import (
    pipeline,
    plugin,
    lib
)


class RedshiftProxyLoader(plugin.HoudiniLoader):
    """Load Redshift Proxy"""

    product_types = {"redshiftproxy"}
    label = "Load Redshift Proxy"
    representations = {"rs"}
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
        container = obj.createNode("geo", node_name=node_name)

        # Check whether the Redshift parameters exist - if not, then likely
        # redshift is not set up or initialized correctly
        if not container.parm("RS_objprop_proxy_enable"):
            container.destroy()
            raise LoadError("Unable to initialize geo node with Redshift "
                            "attributes. Make sure you have the Redshift "
                            "plug-in set up correctly for Houdini.")

        # Enable by default
        container.setParms({
            "RS_objprop_proxy_enable": True,
            "RS_objprop_proxy_file": self.format_path(
                self.filepath_from_context(context),
                context["representation"])
        })

        # Remove the file node, it only loads static meshes
        # Houdini 17 has removed the file node from the geo node
        file_node = container.node("file1")
        if file_node:
            file_node.destroy()

        # Add this stub node inside so it previews ok
        proxy_sop = container.createNode("redshift_proxySOP",
                                         node_name=node_name)
        proxy_sop.setDisplayFlag(True)

        nodes = [container, proxy_sop]

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
        repre_entity = context["representation"]
        # Update the file path
        file_path = self.filepath_from_context(context)

        node = container["node"]
        node.setParms({
            "RS_objprop_proxy_file": self.format_path(
                file_path, repre_entity)
        })

        # Update attribute
        node.setParms({"representation": repre_entity["id"]})

    def remove(self, container):
        node = container["node"]
        node.destroy()

    @staticmethod
    def format_path(path, representation):
        """Format file path correctly for single redshift proxy
        or redshift proxy sequence."""
        # The path is either a single file or sequence in a folder.
        is_sequence = bool(representation["context"].get("frame"))
        if is_sequence:
            path = RedshiftProxyLoader.replace_with_frame_token(path)

        path = os.path.normpath(path)
        path = path.replace("\\", "/")
        return path

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

