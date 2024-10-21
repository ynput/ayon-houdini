from collections import defaultdict
import logging

import hou
import pyblish

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext


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


def get_input_rops(ayon_publish_node):
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
    create_context = CreateContext(host)

    # Deactivate all instances except the one from this node.
    for instance in create_context.instances:

        instance["active"] = False
        if instance.get("instance_node") == node_path:
            instance["active"] = True
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

    usp_nodes = get_upstream_nodes(node)
    for p_node in usp_nodes:
        set_ayon_publish_nodes_pre_render_script(p_node, log, val)


def ayon_publish_command():
    """This command is called by the AYON Publish Rop and will trigger
    publish only for this given node."""
    publish(hou.pwd().path())
