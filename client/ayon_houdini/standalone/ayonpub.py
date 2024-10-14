import hou


def get_upstream_nodes(node: hou.Node):
    # Retruns the upstream nodes to a given node
    return [i_node.inputNode() for i_node in node.inputConnections()]


from ayon_houdini.standalone import ayonpub


def get_us_node_grapth(node: hou.Node, root_node: hou.Node = None):
    # get the the upstream nodes untill we find a nother ayonPub node instance
    # deuplicate the nodes in the upstream.
    # format rootNode:{pNode:{pNode},pNode:{pNode:{pNode}}}

    node_info = {}

    node_info[node] = {
        pNode: {}
        for pNode in get_upstream_nodes(node)
        if not (root_node and root_node.type() == pNode.type())
    }

    for pNode in node_info[node]:

        if not root_node:
            root_node = node

        node_info[node].update(get_us_node_grapth(pNode, root_node=root_node))

    return node_info


def print_grapth(graph: dict, depth: int = 0):
    for k, v in graph.items():
        print("-" * depth + k.path())
        print_grapth(v, depth=depth + 1)


def ayon_pub_command():
    print("Current Node: ", hou.pwd())
    parent_nodes = get_us_node_grapth(hou.pwd())
    print_grapth(parent_nodes)
    print()
