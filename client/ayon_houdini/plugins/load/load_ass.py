import os
import re

import hou

from ayon_houdini.api import (
    pipeline,
    plugin
)


class AssLoader(plugin.HoudiniLoader):
    """Load .ass with Arnold Procedural"""

    product_types = {"ass"}
    label = "Load Arnold Procedural"
    representations = {"ass"}
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
        procedural = obj.createNode("arnold::procedural", node_name=node_name)

        procedural.setParms(
            {
                "ar_filename": self.format_path(context)
            })

        nodes = [procedural]
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
        # Update the file path
        procedural = container["node"]
        procedural.setParms({
            "ar_filename": self.format_path(context),
            "representation": context["representation"]["id"]
        })

    def remove(self, container):
        node = container["node"]
        node.destroy()

    def format_path(self, context):
        """Format file path correctly for single ass.* or ass.* sequence.

        Args:
            context (dict): representation context to be loaded.

        Returns:
             str: Formatted path to be used by the input node.

        """
        path = self.filepath_from_context(context)
        # The path is either a single file or sequence in a folder.
        is_sequence = bool(context["representation"]["context"].get("frame"))
        if is_sequence:
            folder, filename = os.path.split(path)
            filename = re.sub(r"(.*)\.(\d+)\.(ass.*)", "\\1.$F4.\\3", filename)
            path = os.path.join(folder, filename)

        path = os.path.normpath(path)
        path = path.replace("\\", "/")
        return path

    def switch(self, container, context):
        self.update(container, context)
