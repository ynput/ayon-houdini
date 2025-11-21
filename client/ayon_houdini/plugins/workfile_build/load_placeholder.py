from functools import partial

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
        self.transfer_parm_references(placeholder_node, node)

    def transfer_node_connections(self, source_node, target_node):
        # Transfer input connections
        for idx in range(len(source_node.inputs())):
            input_node = source_node.input(idx)
            if input_node is not None:
                target_node.setInput(idx, input_node)

        # Transfer output connections
        for output_node in source_node.outputs():
            for idx in range(len(output_node.inputs())):
                if output_node.input(idx) == source_node:
                    output_node.setInput(idx, target_node)

    def transfer_parm_references(self, source_node, target_node):
        """Find any parms being referenced by other nodes on the source node.

        If that parm exists also on the target node, then remap the references
        to start using the target node's parm instead.
        """
        # Opt-out early if no dependent nodes to begin with
        source_node_path = source_node.path()
        dependencies = [
            dependency_node for dependency_node
            in source_node.dependents()
            # Exclude self and its children
            if not dependency_node.path().startswith(source_node_path)
        ]
        if not dependencies:
            return

        # Repath any parm references from the source node
        for source_parm in source_node.parms():
            # Only care if this parm also exists on the target node
            target_parm = target_node.parm(source_parm.name())
            if not target_parm:
                continue

            referencing_parms = source_parm.parmsReferencingThis()
            if not referencing_parms:
                continue

            # Exclude any references from source node OR child nodes (e.g.
            # inner parts of an HDA)
            referencing_parms = [
                parm for parm in referencing_parms
                if not parm.node().path().startswith(source_node_path)
            ]
            if not referencing_parms:
                continue

            for ref_parm in referencing_parms:
                # For now do not support re-pathing expressions, we assume
                # solely simple channel references.
                if ref_parm.keyframes():
                    continue

                src_relative_expr = ref_parm.referenceExpression(source_parm)
                dest_relative_expr = ref_parm.referenceExpression(target_parm)
                src_absolute = source_parm.path()
                dest_absolute = target_parm.path()

                # Update the reference
                original_value = ref_parm.rawValue()
                if not isinstance(original_value, str):
                    # Can't repath non-string values
                    # TODO: Log a warning
                    continue

                # Repath any absolute references or relative expression
                # references from source parm to the target parm if we
                # can find it in the value
                value: str = original_value.replace(
                    src_relative_expr,
                    dest_relative_expr
                ).replace(
                    src_absolute,
                    dest_absolute
                )
                if value != original_value:
                    # Escape characters
                    value = value.replace("`", "\\`").replace('"', '\\"')
                    cmd = (
                        'opparm -r '
                        f'{ref_parm.node().path()} {ref_parm.name()} "{value}"'
                    )
                    if hou.isUIAvailable():
                        # Somehow this only works if we defer it
                        import hdefereval  # noqa
                        hdefereval.executeDeferred(partial(hou.hscript, cmd))
                    else:
                        hou.hscript(cmd)
