import logging
import re

import hou
import pyblish.api
import pyblish.util

from ayon_houdini.api import lib
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext

log = logging.getLogger(__name__)

#: Node type name of the AYON Publish ROP. The lookup is done on the type name
#: only, so it keeps working across HDA namespace and version changes.
AYON_PUBLISH_NODE_NAME = "ayon_publish"


class AyonPublishError(RuntimeError):
    """Raised when a publish triggered from an AYON Publish node fails."""


def is_ayon_publish_node(node) -> bool:
    """Return whether the given node is an AYON Publish ROP node.

    The check is done on the node type name only, so a new HDA namespace or
    version (e.g. ``ynput::dev::ayon_publish::1.7`` -> ``ayon::ayon_publish
    ::1.0``) does not silently stop matching.

    Args:
        node (hou.Node | None): Node to test.

    Returns:
        bool: Whether the node is an AYON Publish ROP node.
    """
    if node is None or node.type().category() != hou.ropNodeTypeCategory():
        return False
    components = node.type().nameComponents()
    # (namespace, namespace, name, version), e.g.
    # ('', 'ayon', 'ayon_publish', '1.0')
    return len(components) == 4 and components[2] == AYON_PUBLISH_NODE_NAME


def publish(node_path: str):
    """Publish the given AYON Publish node.

    This does not save any changed instance data but only does the single
    publish run with the customized data on the instances for that publish run.

    Raises:
        AyonPublishError: When any publish plugin reported an error. The error
            is also set on the node so the ROP shows up as failed.

    """
    node = hou.node(node_path)
    if node is not None:
        # Clear an error left behind by a previous publish run, so a retry
        # does not stay red for a problem that has been fixed.
        node.clearErrors()

    host = registered_host()
    assert host, "No registered host."

    create_context = CreateContext(host)

    # Deactivate all instances except the one from this node.
    for instance in create_context.instances:
        if instance.get("instance_node") == node_path:
            instance["active"] = True
            instance["from_node"] = True
        else:
            instance["active"] = False

    pyblish_context = pyblish.api.Context()
    pyblish_context.data["create_context"] = create_context
    pyblish_context.data["comment"] = "publish from code"
    pyblish_plugins = create_context.publish_plugins

    error_format = "Failed {plugin.__name__}: {error} -- {error.traceback}"

    # filter out the increment plugin because it will cause our export to
    # get out of sync with nodes running later downstream
    # TODO: Implement more optimal way to filter out the workfile increment
    filtered_plugins = [
        plugin
        for plugin in pyblish_plugins
        if "IncrementCurrentFile" not in str(plugin)
    ]

    errors = []
    for result in pyblish.util.publish_iter(pyblish_context, filtered_plugins):
        log.debug(result)
        for record in result["records"]:
            log.debug("%s: %s", result["plugin"].label, record.msg)

        if result["error"]:
            error_message = error_format.format(**result)
            log.error(error_message)
            errors.append(error_message)

    if errors:
        if node is not None:
            node.addError(
                "AYON publish failed: {} error(s), see the log for "
                "details".format(len(errors)))
        raise AyonPublishError(
            "Publishing '{}' failed:\n{}".format(
                node_path, "\n".join(errors)))


def set_ayon_publish_nodes_pre_render_script(
    rop_node: hou.Node, log: logging.Logger, val: str
):
    node_list = [rop_node]
    node_list.extend(rop_node.inputAncestors())
    for node in node_list:

        if is_ayon_publish_node(node):
            node.parm("prerender").set(val)


def get_rop_output(rop: hou.RopNode, frame_range=None) -> list:
    """Returns a list of output files a RopNode will generate on render.

    It will use the frame range and replacement variables.

    Args:
        rop: Rop Node to get output files for.
        frame_range: Optional frame range tuple (start, end, [increment]).
            If not provided, it will use the frame range set on the RopNode.

    Returns:
         List[str]: List of output files from the ROP node.
    """
    renders_range = rop.parm("trange").eval()
    out_parm = lib.get_output_parameter(rop)

    # Render Current Frame
    if frame_range is None and renders_range == 0:
        return [out_parm.eval()]

    # Render Frame Range or Render Frame Range Only
    # Get the file path with $F as format-able part as path template.
    path = lib.evalParmNoFrame(rop, out_parm.name())
    if "#" not in path:
        # Not frame dependent filename, single file
        return [path]

    def replace(match):
        padding = len(match.group(0))
        if padding < 2:
            return "{frame}"
        else:
            return "{{frame:0{padding}d}}".format(padding=padding)

    path_template = re.sub("#+", replace, path)

    inc = rop.parm("f3").eval()
    if frame_range is not None:
        # Use user specified frame range tuple (2 or 3 elements)
        # See Houdini `RopNode.render` arguments
        start = frame_range[0]
        end = frame_range[1]
        if len(frame_range) == 3:
            inc = frame_range[2]
    else:
        start = rop.parm("f1").eval()
        end = rop.parm("f2").eval()

    files = []
    for frame in range(int(start), int(end) + 1, int(inc)):
        files.append(path_template.format(frame=frame))

    return files


def ayon_publish_command():
    """This command is called by the AYON Publish Rop and will trigger
    publish only for this given node."""
    publish(hou.pwd().path())
