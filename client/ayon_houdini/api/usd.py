"""Houdini-specific USD Library functions."""

import contextlib
import logging
import json
import itertools
from typing import List

import hou
import ayon_api
from pxr import Usd, Sdf, Tf, Vt, UsdRender

log = logging.getLogger(__name__)


def add_usd_output_processor(ropnode, processor):
    """Add USD Output Processor to USD Rop node.

    Args:
        ropnode (hou.RopNode): The USD Rop node.
        processor (str): The output processor name. This is the basename of
            the python file that contains the Houdini USD Output Processor.

    """

    import loputils

    loputils.handleOutputProcessorAdd(
        {
            "node": ropnode,
            "parm": ropnode.parm("outputprocessors"),
            "script_value": processor,
        }
    )


def remove_usd_output_processor(ropnode, processor):
    """Removes USD Output Processor from USD Rop node.

    Args:
        ropnode (hou.RopNode): The USD Rop node.
        processor (str): The output processor name. This is the basename of
            the python file that contains the Houdini USD Output Processor.

    """
    import loputils

    parm = ropnode.parm(processor + "_remove")
    if not parm:
        raise RuntimeError(
            "Output Processor %s does not "
            "exist on %s" % (processor, ropnode.name())
        )

    loputils.handleOutputProcessorRemove({"node": ropnode, "parm": parm})


@contextlib.contextmanager
def outputprocessors(ropnode, processors=tuple(), disable_all_others=True):
    """Context manager to temporarily add Output Processors to USD ROP node.

    Args:
        ropnode (hou.RopNode): The USD Rop node.
        processors (tuple or list): The processors to add.
        disable_all_others (bool, Optional): Whether to disable all
            output processors currently on the ROP node that are not in the
            `processors` list passed to this function.

    """
    # TODO: Add support for forcing the correct Order of the processors

    original = []
    prefix = "enableoutputprocessor_"
    processor_parms = ropnode.globParms(prefix + "*")
    for parm in processor_parms:
        original.append((parm, parm.eval()))

    if disable_all_others:
        for parm in processor_parms:
            parm.set(False)

    added = []
    for processor in processors:

        parm = ropnode.parm(prefix + processor)
        if parm:
            # If processor already exists, just enable it
            parm.set(True)

        else:
            # Else add the new processor
            add_usd_output_processor(ropnode, processor)
            added.append(processor)

    try:
        yield
    finally:

        # Remove newly added processors
        for processor in added:
            remove_usd_output_processor(ropnode, processor)

        # Revert to original values
        for parm, value in original:
            if parm:
                parm.set(value)


def get_usd_rop_loppath(node):

    # Get sop path
    node_type = node.type().name()
    if node_type in {"usd", "usdrender"}:
        return node.parm("loppath").evalAsNode()

    elif node_type in {"usd_rop", "usdrender_rop"}:
        # Inside Solaris e.g. /stage (not in ROP context)
        # When incoming connection is present it takes it directly
        inputs = node.inputs()
        if inputs:
            return inputs[0]
        else:
            return node.parm("loppath").evalAsNode()


def get_layer_save_path(layer, expand_string=True):
    """Get custom HoudiniLayerInfo->HoudiniSavePath from SdfLayer.

    Args:
        layer (pxr.Sdf.Layer): The Layer to retrieve the save pah data from.
        expand_string (bool): Whether to expand any houdini vars in the save
            path before computing the absolute path.

    Returns:
        str or None: Path to save to when data exists.

    """
    hou_layer_info = layer.rootPrims.get("HoudiniLayerInfo")
    if not hou_layer_info:
        return

    save_path = hou_layer_info.customData.get("HoudiniSavePath", None)
    if save_path:
        # Unfortunately this doesn't actually resolve the full absolute path
        if expand_string:
            save_path = hou.text.expandString(save_path)
        return layer.ComputeAbsolutePath(save_path)


def get_referenced_layers(layer):
    """Return SdfLayers for all external references of the current layer

    Args:
        layer (pxr.Sdf.Layer): The Layer to retrieve the save pah data from.

    Returns:
        list: List of pxr.Sdf.Layer that are external references to this layer

    """

    layers = []
    for layer_id in layer.GetExternalReferences():
        layer = Sdf.Layer.Find(layer_id)
        if not layer:
            # A file may not be in memory and is
            # referenced from disk. As such it cannot
            # be found. We will ignore those layers.
            continue

        layers.append(layer)

    return layers


def iter_layer_recursive(layer):
    """Recursively iterate all 'external' referenced layers"""

    layers = get_referenced_layers(layer)
    traversed = set(layers)  # Avoid recursion to itself (if even possible)
    traverse = list(layers)
    for layer in traverse:

        # Include children layers (recursion)
        children_layers = get_referenced_layers(layer)
        children_layers = [x for x in children_layers if x not in traversed]
        traverse.extend(children_layers)
        traversed.update(children_layers)

        yield layer


def get_configured_save_layers(usd_rop, strip_above_layer_break=True):
    """Retrieve the layer save paths from a USD ROP.

    Arguments:
        usdrop (hou.RopNode): USD Rop Node
        strip_above_layer_break (Optional[bool]): Whether to exclude any
            layers that are above layer breaks. This defaults to True.

    Returns:
        List[Sdf.Layer]: The layers with configured save paths.

    """

    lop_node = get_usd_rop_loppath(usd_rop)
    stage = lop_node.stage(apply_viewport_overrides=False)
    if not stage:
        raise RuntimeError(
            "No valid USD stage for ROP node: " "%s" % usd_rop.path()
        )

    root_layer = stage.GetRootLayer()

    if strip_above_layer_break:
        layers_above_layer_break = set(lop_node.layersAboveLayerBreak())
    else:
        layers_above_layer_break = set()

    save_layers = []
    for layer in iter_layer_recursive(root_layer):
        if (
            strip_above_layer_break and
            layer.identifier in layers_above_layer_break
        ):
            continue

        save_path = get_layer_save_path(layer)
        if save_path is not None:
            save_layers.append(layer)

    return save_layers


def setup_lop_python_layer(layer, node, savepath=None,
                           apply_file_format_args=True):
    """Set up Sdf.Layer with HoudiniLayerInfo prim for metadata.

    This is the same as `loputils.createPythonLayer` but can be run on top
    of `pxr.Sdf.Layer` instances that are already created in a Python LOP node.
    That's useful if your layer creation itself is built to be DCC agnostic,
    then we just need to run this after per layer to make it explicitly
    stored for houdini.

    By default, Houdini doesn't apply the FileFormatArguments supplied to
    the created layer; however it does support USD's file save suffix
    of `:SDF_FORMAT_ARGS:` to supply them. With `apply_file_format_args` any
    file format args set on the layer's creation will be added to the
    save path through that.

    Note: The `node.addHeldLayer` call will only work from a LOP python node
        whenever `node.editableStage()` or `node.editableLayer()` was called.

    Arguments:
        layer (Sdf.Layer): An existing layer (most likely just created
            in the current runtime)
        node (hou.LopNode): The Python LOP node to attach the layer to so
            it does not get garbage collected/mangled after the downstream.
        savepath (Optional[str]): When provided the HoudiniSaveControl
            will be set to Explicit with HoudiniSavePath to this path.
        apply_file_format_args (Optional[bool]): When enabled any
            FileFormatArgs defined for the layer on creation will be set
            in the HoudiniSavePath so Houdini USD ROP will use them top.

    Returns:
        Sdf.PrimSpec: The Created HoudiniLayerInfo prim spec.

    """
    # Add a Houdini Layer Info prim where we can put the save path.
    p = Sdf.CreatePrimInLayer(layer, '/HoudiniLayerInfo')
    p.specifier = Sdf.SpecifierDef
    p.typeName = 'HoudiniLayerInfo'
    if savepath:
        if apply_file_format_args:
            args = layer.GetFileFormatArguments()
            savepath = Sdf.Layer.CreateIdentifier(savepath, args)

        p.customData['HoudiniSavePath'] = savepath
        p.customData['HoudiniSaveControl'] = 'Explicit'
    # Let everyone know what node created this layer.
    p.customData['HoudiniCreatorNode'] = node.sessionId()
    p.customData['HoudiniEditorNodes'] = Vt.IntArray([node.sessionId()])
    node.addHeldLayer(layer.identifier)

    return p


@contextlib.contextmanager
def remap_paths(rop_node, mapping):
    """Enable the AyonRemapPaths output processor with provided `mapping`"""
    from ayon_houdini.api.lib import parm_values

    if not mapping:
        # Do nothing
        yield
        return

    # Houdini string parms need to escape backslashes due to the support
    # of expressions - as such we do so on the json data
    value = json.dumps(mapping).replace("\\", "\\\\")
    with outputprocessors(
        rop_node,
        processors=["ayon_remap_paths"],
        disable_all_others=True,
    ):
        with parm_values([
            (rop_node.parm("ayon_remap_paths_remap_json"), value)
        ]):
            yield


def get_usd_render_rop_rendersettings(rop_node, stage=None, logger=None):
    """Return the chosen UsdRender.Settings from the stage (if any).

    Args:
        rop_node (hou.Node): The Houdini USD Render ROP node.
        stage (pxr.Usd.Stage): The USD stage to find the render settings
             in. This is usually the stage from the LOP path the USD Render
             ROP node refers to.
        logger (logging.Logger): Logger to log warnings to if no render
            settings were find in stage.

    Returns:
        Optional[UsdRender.Settings]: Render Settings.

    """
    if logger is None:
        logger = log

    if stage is None:
        lop_node = get_usd_rop_loppath(rop_node)
        stage = lop_node.stage()

    path = rop_node.evalParm("rendersettings")
    if not path:
        # Default behavior
        path = "/Render/rendersettings"

    prim = stage.GetPrimAtPath(path)
    if not prim:
        logger.warning("No render settings primitive found at: %s", path)
        return

    render_settings = UsdRender.Settings(prim)
    if not render_settings:
        logger.warning("Prim at %s is not a valid RenderSettings prim.", path)
        return

    return render_settings


def get_schema_type_names(type_name: str) -> List[str]:
    """Return schema type name for type name and its derived types

    This can be useful for checking whether a `Sdf.PrimSpec`'s type name is of
    a given type or any of its derived types.

    Args:
        type_name (str): The type name, like e.g. 'UsdGeomMesh'

    Returns:
        List[str]: List of schema type names and their derived types.

    """
    schema_registry = Usd.SchemaRegistry
    type_ = Tf.Type.FindByName(type_name)

    if type_ == Tf.Type.Unknown:
        type_ = schema_registry.GetTypeFromSchemaTypeName(type_name)
        if type_ == Tf.Type.Unknown:
            # Type not found
            return []

    results = []
    derived = type_.GetAllDerivedTypes()
    for derived_type in itertools.chain([type_], derived):
        schema_type_name = schema_registry.GetSchemaTypeName(derived_type)
        if schema_type_name:
            results.append(schema_type_name)

    return results


def get_ayon_entity_uri_from_representation_context(context: dict) -> str:
    """Resolve AYON Entity URI from representation context.

    Note:
        The representation context is the `get_representation_context` dict
        containing the `project`, `folder, `representation` and so forth.
        It is not the representation entity `context` key.

    Arguments:
        context (dict): The representation context.

    Raises:
        RuntimeError: Unable to resolve to a single valid URI.

    Returns:
        str: The AYON entity URI.

    """
    project_name = context["project"]["name"]
    representation_id = context["representation"]["id"]
    response = ayon_api.post(
        f"projects/{project_name}/uris",
        entityType="representation",
        ids=[representation_id])
    if response.status_code != 200:
        raise RuntimeError(
            f"Unable to resolve AYON entity URI for '{project_name}' "
            f"representation id '{representation_id}': {response.text}"
        )
    uris = response.data["uris"]
    if len(uris) != 1:
        raise RuntimeError(
            f"Unable to resolve AYON entity URI for '{project_name}' "
            f"representation id '{representation_id}' to single URI. "
            f"Received data: {response.data}"
        )
    return uris[0]["uri"]
