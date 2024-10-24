from collections import defaultdict
import logging
import re
import os

import hou
import pyblish

from ayon_houdini.api import lib
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext


import importlib

importlib.reload(lib)


def get_input_ancestors(start_node: hou.Node, filter_fn=None, as_graph=False):
    """Return all the input ancestors of the given node.

    This is similar to `hou.OpNode.inputAncestors()`, but allows for filtering
    out certain nodes based on a filter function. The upstream detection will
    stop at the filtered nodes.

    When `as_graph` is True, the function will return a nested dictionary of
    the input ancestors. Otherwise, it will return a flat list of all the
    inputs.

    """
    graph = defaultdict(dict)
    processed = set()
    queue = [start_node]

    for node in queue:
        # Avoid recursion in recursive networks
        if node in processed:
            continue

        processed.add(node)
        for upstream_node in node.inputs():
            # Ignore upstream node if it's to be filtered out
            if filter_fn and filter_fn(upstream_node):
                continue

            graph[node][upstream_node] = graph[upstream_node]
            if upstream_node in processed:
                continue
            queue.append(upstream_node)

    if as_graph:
        return graph[start_node]
    else:
        processed.remove(start_node)
        return list(processed)


def get_input_rops(ayon_publish_node: hou.Node):
    """Return all inputs ROPs we consider part of this AYON Publish node."""
    stop_node_type = ayon_publish_node.type()
    return get_input_ancestors(
        ayon_publish_node,
        # Stop at nodes of the same type
        filter_fn=lambda node: node.type() == stop_node_type,
        as_graph=False,
    )


# TODO: Remove the graph functionality unless we have a use-case for this?
def get_upstream_node_graph(start_node: hou.Node):
    # Return upstream nodes until we find another node of the same node type
    start_node_type = start_node.type()
    return get_input_ancestors(
        start_node,
        # Stop at nodes of the same type
        filter_fn=lambda node: node.type() == start_node_type,
        as_graph=True,
    )


def format_graph(graph: dict, depth: int = 0) -> str:
    """Format the graph output to a human-readable printable string."""
    out_string = ""
    for k, v in graph.items():
        out_string = out_string + ("-" * depth + k.path()) + "\n"
        out_string = out_string + format_graph(v, depth=depth + 1) + "\n"
    return out_string


def publish(node_path: str):
    """Publish the given AYON Publish node."""
    host = registered_host()
    assert host, "No registered host."

    logging.basicConfig()
    log = logging.getLogger("publish-from-code")
    log.setLevel(logging.ERROR)

    deactivated_instances = []
    from_code_instances = []
    create_context = CreateContext(host)

    # Deactivate all instances except the one from this node.
    for instance in create_context.instances:

        if instance.get("instance_node") == node_path:
            instance["active"] = True
            instance["from_node"] = True
            from_code_instances.append(instance)
        else:
            if instance["active"]:
                deactivated_instances.append(instance)
            instance["active"] = False

    create_context.save_changes()

    pyblish_context = pyblish.api.Context()
    pyblish_context.data["create_context"] = create_context
    pyblish_context.data["comment"] = "publish from code"
    pyblish_plugins = create_context.publish_plugins

    error_format = "Failed {plugin.__name__}: {error} -- {error.traceback}"
    for result in pyblish.util.publish_iter(pyblish_context, pyblish_plugins):
        for record in result["records"]:
            log.debug("{}: {}".format(result["plugin"].label, record.msg))

        # Exit as soon as any error occurs.
        if result["error"]:
            error_message = error_format.format(**result)
            log.debug(error_message)
    for instance in from_code_instances:
        instance["from_node"] = False
    for instance in deactivated_instances:
        instance["active"] = True

    create_context.save_changes()


def set_ayon_publish_nodes_pre_render_script(
    node: hou.Node, log: logging.Logger, val: str
):
    if node.type() == hou.nodeType(
        hou.ropNodeTypeCategory(), "ynput::dev::ayon_publish::1.7"
    ):
        node.parm("prerender").set(val)

    usp_nodes = get_input_rops(node)
    for p_node in usp_nodes:
        set_ayon_publish_nodes_pre_render_script(p_node, log, val)


frame_var_regx = r"\$F(?:\d*|F)"


def get_rop_output(rop: hou.RopNode) -> list:
    """returns a list of output files a Given node will generated based on Frame range and replacement Varaibles

    Args:
        rop: input Rop Node



    Returns (list:str): list of strings with the output files. Empty list if its not possible to evaluate the output

    """
    out_parm = lib.get_output_parameter(rop)

    renders_range = rop.parm("trange").eval()
    if 0:  # Render Current Frame
        return [out_parm.eval()]
        # just evaluate the parm
    elif 1 or 2:  # Render Frame Range or Render Frame Range Only
        raw_out = out_parm.rawValue()

        match = re.findall(frame_var_regx, raw_out)
        if not match:
            # if no Range parms exist we just return the eveluated parm
            return [out_parm.eval()]

        start = rop.parm("f1").eval()
        end = rop.parm("f2").eval()
        inc = rop.parm("f3").eval()
        out_list = []
        for frame in range(int(start), int(end), int(inc)):
            frame_out_parm = raw_out
            for i in match:
                frame_out_parm = frame_out_parm.replace(i, str(frame))

            # TODO move this before the loop as we can eveluate all Vars execpt $F
            frame_out_parm = frame_out_parm.replace(
                "$OS", rop.name()
            )  # TODO find out why expandString replaces $OS with Director and not the actual node name
            frame_out_parm = hou.expandString(frame_out_parm)

            out_list.append(frame_out_parm)

        return out_list
        # get start end frame range
        # get increment
        # resolve Hou env variables (hou.expandString('$HIP'))
        # replace $F $F4 varialbes with numbers
        # resolve the $F $F4 varialbe
    return []


def ayon_publish_command():
    """This command is called by the AYON Publish Rop and will trigger
    publish only for this given node."""

    # for i in get_input_rops(hou.pwd()):
    #     print(lib.get_output_parameter(i))

    publish(hou.pwd().path())
