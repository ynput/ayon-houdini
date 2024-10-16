import hou
import os
import pyblish
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext
import logging


def get_upstream_nodes(node: hou.Node):
    # Retruns the upstream nodes to a given node
    return [i_node.inputNode() for i_node in node.inputConnections()]


def get_us_node_graph(node: hou.Node, root_node: hou.Node = None):
    # get the the upstream nodes untill we find a nother ayonPub node instance
    # deuplicate the nodes in the upstream.
    # format rootNode:{pNode:{pNode},pNode:{pNode:{pNode}}}

    node_info = {}

    node_info[node] = {
        pNode: {}
        for pNode in get_upstream_nodes(node)
        if not (root_node and root_node.type() == pNode.type())
    }
    from pprint import pprint

    for pNode in node_info[node]:

        if not root_node:
            root_node = node

        node_info[node].update(get_us_node_graph(pNode, root_node=root_node))

    return node_info


def print_grapth(graph: dict, depth: int = 0):
    out_string = ""
    for k, v in graph.items():
        out_string = out_string + ("-" * depth + k.path()) + "\n"
        out_string = out_string + print_grapth(v, depth=depth + 1) + "\n"
    return out_string


def get_graph_output(graph: dict):
    files = []
    for node, child in graph.items():
        try:
            files.append(node.parm("sopoutput").eval())
        except AttributeError:
            pass

        files.extend(get_graph_output(child))
    return files


def pub(node_path: str):
    host = registered_host()

    assert host, "No registered host."

    logging.basicConfig()
    log = logging.getLogger("publish-from-code")
    log.setLevel(logging.ERROR)

    create_context = CreateContext(host)

    for instance in create_context.instances:
        instance["active"] = False
        if instance["instance_id"] == node_path:
            instance["active"] = True

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


def ayon_publish_command():
    """this command is called by the ayon_pub rop and will trigger publish only for this given node."""
    # print("Current Node: ", hou.pwd())
    pub(hou.pwd().path())
    # parent_nodes = get_us_node_graph(hou.pwd())
    # for i in get_graph_output(parent_nodes):
    #     print(i.split(".")[0])
    # print(print_grapth(parent_nodes))
    print()
