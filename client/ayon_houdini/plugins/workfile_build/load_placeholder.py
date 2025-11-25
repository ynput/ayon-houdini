from ayon_core.pipeline.workfile.workfile_template_builder import (
    LoadPlaceholderItem,
    PlaceholderLoadMixin,
)

from ayon_houdini.api.workfile_template_builder import (
    HoudiniPlaceholderPlugin
)
from ayon_houdini.api.plugin import HoudiniCreator

import hou


class HoudiniPlaceholderLoadPlugin(
    HoudiniPlaceholderPlugin, PlaceholderLoadMixin
):
    """Workfile template plugin to create "load placeholders".

    "load placeholders" will be replaced by AYON products.

    """

    identifier = "ayon.load.placeholder"
    label = "Houdini Load"

    def create_placeholder(self, placeholder_data):
        node_name = self.get_placeholder_node_name(placeholder_data)
        # Create a placeholder node that can actually act as stub inside
        # a Houdini scene with the real deal, including input/output
        # connections
        loader_name: str = placeholder_data["loader"]
        loaders_by_name = self.builder.get_loaders_by_name()
        loader = loaders_by_name[loader_name]

        # Allow Loader plug-ins to define what kind of placeholder node to
        # create so they are relevant to the node context that eventually
        # gets created by the loader.
        if hasattr(loader, "create_load_placeholder_node"):
            placeholder_node = loader().create_load_placeholder_node(
                node_name,
                placeholder_data
            )
        else:
            placeholder_node = self.create_placeholder_node(node_name)

        HoudiniCreator.customize_node_look(placeholder_node)

        placeholder_data["plugin_identifier"] = self.identifier
        self._imprint(placeholder_node, placeholder_data)

    def populate_placeholder(self, placeholder):
        self.populate_load_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        self.populate_load_placeholder(placeholder)

    def get_placeholder_options(self, options=None):
        return self.get_load_plugin_options(options)

    def get_placeholder_node_name(self, placeholder_data):
        node_name = "{}_{}".format(
            self.identifier.replace(".", "_"),
            placeholder_data["product_name"]
        )
        return node_name

    def collect_placeholders(self):
        output = []
        load_placeholders = self.collect_scene_placeholders()

        for node in load_placeholders:
            placeholder_data = self._read(node)
            output.append(
                LoadPlaceholderItem(node.path(), placeholder_data, self)
            )

        return output

    # Take control of loaded repre data
    def load_succeed(self, placeholder, container):
        # Move the container to the placeholder and transfer connections
        placeholder_node = hou.node(placeholder.scene_identifier)
        target_context = placeholder_node.parent()

        # If placeholder node is an object merge then do not move the container
        # node, but instead set the object merge to point to the container node
        if placeholder_node.type().name() == "object_merge":
            name = container.name().removesuffix("_CON")
            node = target_context.createNode(
                "object_merge",
                node_name=name,
                force_valid_node_name=True
            )
            node.setParms({
                "objpath1": container.path()
            })
        else:
            if container.parent() == target_context:
                node = container
            else:
                node = hou.moveNodesTo(
                    [container],
                    target_context,
                )[0]

        node.setPosition(placeholder_node.position())

        self.transfer_node_connections(placeholder_node, node)

    def transfer_node_connections(self, source_node, target_node):
        """Transfer input and output connections from source to target node.

        The source node is the placeholder node.
        The target node is the loaded container node.
        """
        # Transfer input connections
        for conn in source_node.inputConnections():
            target_node.setInput(
                conn.inputIndex(),
                conn.inputNode(),
                conn.outputIndex(),
            )

        # Transfer output connections
        for conn in source_node.outputConnections():
            # When going through `merge` target nodes insert new
            # connections so multiple loaded placeholders can all add into
            # a single merge.
            output_node = conn.outputNode()
            if output_node.type().name() == "merge":
                # Insert the connection after the placeholder connection
                output_node.insertInput(
                    conn.inputIndex() + 1,
                    target_node,
                    conn.outputIndex(),
                )
            else:
                output_node.setInput(
                    conn.inputIndex(),
                    target_node,
                    conn.outputIndex(),
                )
