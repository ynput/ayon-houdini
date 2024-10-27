import json
import contextlib

import hou
from pxr import Sdf, Usd
import pyblish.api

from ayon_houdini.api import plugin
from ayon_houdini.api.lib import (
    get_lops_rop_context_options,
    context_options,
    update_mode_context
)


def copy_stage_layers(stage) -> dict[Sdf.Layer, Sdf.Layer]:
    # Create a mapping from original layers to their copies
    layer_mapping = {}

    # Copy each layer
    for layer in stage.GetLayerStack(includeSessionLayers=False):
        # It seems layer.IsAnonymous() fails (does not exist yet?) so we use
        # the identifier to check if it is an anonymous layer
        if not Sdf.Layer.IsAnonymousLayerIdentifier(layer.identifier):
            # We disregard non-anonmyous layers for replacing and assume
            # they are static enough for our use case.
            continue

        # Sdf.Layer.TransferContent seems to crash, so instead we export
        # and import (serialize/deserialize) to make a unique copy.
        layer_str = layer.ExportToString()
        copied_layer = Sdf.Layer.CreateAnonymous()
        copied_layer.ImportFromString(layer_str)
        layer_mapping[layer] = copied_layer

    # Remap all used layers in the root layer
    # TODO: Confirm whether this is technically sufficient?
    copied_root_layer = layer_mapping[stage.GetRootLayer()]
    for old_layer, new_layer in layer_mapping.items():
        copied_root_layer.UpdateCompositionAssetDependency(
            old_layer.identifier,
            new_layer.identifier
        )

    return layer_mapping


class CollectUsdRenderLayerAndStage(plugin.HoudiniInstancePlugin):
    """Collect USD stage and layers below layer break for USD ROPs.

    This collects an in-memory copy of the Usd.Stage that can be used in other
    collectors and validations. It also collects the Sdf.Layer objects up to
    the layer break (ignoring any above).

    It only creates an in-memory copy of anonymous layers and assumes that any
    intended to live on disk are already static written to disk files or at
    least the loaded Sdf.Layer to not be updated during publishing.

    It collects the stage and layers from the LOP node connected to the USD ROP
    with the context options set on the ROP node. This ensures the graph is
    evaluated similar to how the ROP node would process it on export.

    """

    label = "Collect ROP Sdf Layers and USD Stage"
    # Run after Collect Output Node
    order = pyblish.api.CollectorOrder
    hosts = ["houdini"]
    families = ["usdrender", "usdrop"]

    def process(self, instance):

        lop_node = instance.data.get("output_node")
        if not lop_node:
            return

        lop_node: hou.LopNode
        rop: hou.RopNode = hou.node(instance.data["instance_node"])
        options = get_lops_rop_context_options(rop)

        # Log the context options
        self.log.debug(
            "Collecting USD stage with context options:\n"
            f"{json.dumps(options, indent=4)}")

        with contextlib.ExitStack() as stack:
            # Force cooking the lop node does not seem to work, so we
            # must set the cook mode to "Update" for this to work
            stack.enter_context(update_mode_context(hou.updateMode.AutoUpdate))

            # Set the context options of the ROP node.
            stack.enter_context(context_options(options))

            # Get stage and layers from the LOP node.
            stage = lop_node.stage(use_last_cook_context_options=False,
                                   apply_viewport_overrides=False,
                                   apply_post_layers=False)
            above_break_layers = set(lop_node.layersAboveLayerBreak(
                use_last_cook_context_options=False))
            layers = [
                layer for layer
                in stage.GetLayerStack(includeSessionLayers=False)
                if layer.identifier not in above_break_layers
            ]

            # The returned stage and layer in memory is shared across cooks
            # so it is the exact same stage and layer object each time if
            # multiple ROPs point to the same LOP node (or its layer's graph).
            # As such, we must explicitly copy the stage and layers to ensure
            # the next 'cook' does not affect the stage and layers of the
            # previous instance or by any other process down the line.
            # Get a copy of the stage and layers so that any in houdini edit
            # or another recook from another instance of the same LOP layers
            # does not influence this collected stage and layers.
            copied_layer_mapping = copy_stage_layers(stage)
            copied_stage = Usd.Stage.Open(
                copied_layer_mapping[stage.GetRootLayer()])
            copied_layers = [
                # Remap layers only that were remapped (anonymous layers
                # only). If the layer was not remapped, then use the
                # original
                copied_layer_mapping.get(layer, layer) for layer in layers
            ]

            instance.data["layers"] = copied_layers
            instance.data["stage"] = copied_stage