import json
import logging
import os
import re

import hou
import pyblish.api

from ayon_houdini.api import lib
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext
from ayon_core.pipeline.publish import PublishError, PublishLogic

log = logging.getLogger(__name__)

#: Node type name of the AYON Publish ROP. The lookup is done on the type name
#: only, so it keeps working across HDA namespace and version changes.
AYON_PUBLISH_NODE_NAME = "ayon_publish"

#: Creator identifier of the AYON Publish ROP creator. Unlike the publish
#: family this does not change when another product type (and thereby another
#: product base type) is selected on the ROP.
AYON_PUBLISH_CREATOR_IDENTIFIER = "io.ayon.creators.houdini.rop_publish"

#: Node user data key storing the appearance of the node before it was
#: marked as failed by :func:`set_node_error`.
NODE_ERROR_STATE_KEY = "ayon_publish_error_state"

#: Color used to mark an AYON Publish node that failed to publish.
NODE_ERROR_COLOR = hou.Color((1.0, 0.2, 0.2))


def set_node_error(node: "hou.Node | None", message: str) -> None:
    """Display an error state on an AYON Publish node.

    Houdini's :meth:`hou.OpNode.addError` may only be called on a node that
    is currently cooking, so it cannot be relied upon from the publish or
    pre-render context. Instead the node gets an error color and comment.
    The original appearance is remembered in the node's user data so that
    :func:`clear_node_error` can restore it.

    Args:
        node (hou.Node | None): Node to mark as failed.
        message (str): Error message to display on the node.
    """
    if node is None:
        return

    # Remember the original color and comment only once, so repeated
    # failures do not overwrite the state we need to restore later.
    if not node.userDataDict().get(NODE_ERROR_STATE_KEY):
        state = {
            "color": list(node.color().rgb()),
            "comment": node.comment() or "",
        }
        node.setUserData(NODE_ERROR_STATE_KEY, json.dumps(state))

    node.setColor(NODE_ERROR_COLOR)
    node.setComment("AYON publish FAILED: {}".format(message))

    # `addError` is only allowed while the node is cooking, so treat the
    # error badge as best effort; the color and comment above always show.
    try:
        node.addError(message)
    except Exception:
        log.debug(
            "Could not add error badge to '%s'", node.path(),
            exc_info=True,
        )


def clear_node_error(node: "hou.Node | None") -> None:
    """Clear the error state of an AYON Publish node.

    Restores the node color and comment that were present before
    :func:`set_node_error` was called.

    Args:
        node (hou.Node | None): Node to clear the error state on.
    """
    if node is None:
        return

    # `clearErrors` is not available on all Houdini versions (and may be a
    # no-op outside a cook), so guard the call.
    clear_errors = getattr(node, "clearErrors", None)
    if clear_errors is not None:
        try:
            clear_errors()
        except Exception:
            log.debug(
                "Could not clear node errors on '%s'", node.path(),
                exc_info=True,
            )

    stored = node.userDataDict().get(NODE_ERROR_STATE_KEY)
    if not stored:
        return

    try:
        state = json.loads(stored)
    except (TypeError, ValueError):
        state = {}

    color = state.get("color")
    if isinstance(color, (list, tuple)) and len(color) == 3:
        node.setColor(hou.Color(tuple(color)))
    node.setComment(state.get("comment", ""))
    node.setUserData(NODE_ERROR_STATE_KEY, "")


def is_rop_publish_instance(instance) -> bool:
    """Return whether the given instance is published by an AYON Publish ROP.

    AYON Publish ROP instances can carry additional product type families
    (e.g. "model" or "pointcache") because the product type is chosen on the
    ROP. Those families are not backed by a native ROP node, so the native
    Houdini ROP publish plugins must not process these instances: their
    output is collected by ``CollectAYONPublishOutputs`` instead.

    Instances are recognized by the AYON Publish creator identifier, which
    stays the same when a different product type is selected, and which also
    differs from the identifiers of the native ROP creators.

    Args:
        instance (pyblish.api.Instance): Instance to test.

    Returns:
        bool: Whether the instance is an AYON Publish ROP instance.
    """
    instance_data = instance.data
    return (
        instance_data.get("creator_identifier")
        == AYON_PUBLISH_CREATOR_IDENTIFIER
    )


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


#: Product types offered by the AYON Publish ROP. The generic "rop_publish"
#: type is always offered first so that it remains the default.
#:
#: TODO: "pointcache" and "vdbcache" are planned to move to a dedicated AYON
#:   ROP Cache node in a separate PR. They stay selectable here until that
#:   node exists.
DEFAULT_PRODUCT_TYPES = (
    "rop_publish",
    "model",
    "pointcache",
    "fbx",
    "render",
    "review",
    "usd",
    "vdbcache",
    "look",
)


def get_product_types() -> list[tuple[str, str]]:
    """Return the product types selectable on the AYON Publish ROP.

    The common AYON product types are offered, with the generic
    ``rop_publish`` product type first so that it remains the default.
    Product type items can be customized through the creator settings.

    Returns:
        list[tuple[str, str]]: Product type name and label pairs.
    """
    return [(name, name) for name in DEFAULT_PRODUCT_TYPES]


def get_product_type_menu() -> list[str]:
    """Return dynamic Houdini menu items for the ROP productType parameter.

    The menu items alternate between value and label, as expected by a
    Houdini dynamic menu (``menureplace``) callback.

    Returns:
        list[str]: Alternating product type value and label entries.
    """
    menu = []
    for value, label in get_product_types():
        menu.extend([value, label])
    return menu


def publish(node_path: str, report_path: "str | None" = None) -> dict:
    """Publish the given AYON Publish node.

    This does not save any changed instance data but only does the single
    publish run with the customized data on the instances for that publish run.

    The JSON publish report (the same data the Publisher UI can store) is
    returned and, when a report path is provided, stored to that file. The
    report is stored even when publishing fails.

    Args:
        node_path (str): Path to the AYON Publish ROP node to publish.
        report_path (str | None): Path where the JSON publish report is stored.
            Can also be set with the ``AYON_PUBLISH_REPORT_PATH`` environment
            variable, which is useful for farm renders.

    Returns:
        dict: JSON publish report data.

    Raises:
        PublishError: When any publish plugin reported an error. The error
            is also set on the node so the ROP shows up as failed.

    """
    node = hou.node(node_path)
    if node is not None:
        # Clear an error state left behind by a previous publish run, so a
        # retry does not stay marked as failed for a fixed problem.
        clear_node_error(node)

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

    # filter out the increment plugin because it will cause our export to
    # get out of sync with nodes running later downstream
    # TODO: Implement more optimal way to filter out the workfile increment
    filtered_plugins = [
        plugin
        for plugin in create_context.publish_plugins
        if "IncrementCurrentFile" not in str(plugin)
    ]

    project_name = (
        create_context.get_current_project_name()
        or os.environ.get("AYON_PROJECT_NAME")
    )
    logic = PublishLogic(reset=False)
    logic.reset(
        project_name,
        context=pyblish_context,
        plugins=filtered_plugins,
        create_context=create_context,
    )
    logic.publish()

    report_data = logic.get_publish_report_data()

    if report_path is None:
        report_path = os.environ.get("AYON_PUBLISH_REPORT_PATH")
    if report_path:
        report_path = os.path.abspath(os.path.expanduser(report_path))
        report_dir = os.path.dirname(report_path)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        logic.store_publish_report(report_path)
        log.info(f"Publish report stored to '{report_path}'")

    if logic.has_failed():
        errors = []
        for error_info in logic.iter_all_error_info():
            message = _format_publish_error(error_info)
            log.error(message)
            errors.append(message)

        if not errors:
            errors.append(
                f"Publishing failed: {logic.get_fail_reason()}"
            )

        set_node_error(
            node,
            f"{len(errors)} error(s), see the log for details",
        )
        error_message = "\n".join(errors)
        raise PublishError(
            f"Publishing '{node_path}' failed:\n{error_message}")

    return report_data


def _format_publish_error(error_info) -> str:
    """Format a publish error info item into a readable log message.

    Args:
        error_info: Publish error information item.

    Returns:
        str: Readable error message.
    """
    title = error_info.title or "Publish error"
    description = error_info.description or str(error_info.exception)
    detail = error_info.detail
    if detail:
        description = f"{description}\n{detail}"
    return f"{title}: {description}"


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
