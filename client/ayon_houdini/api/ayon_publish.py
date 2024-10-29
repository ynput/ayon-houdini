import logging
import re
import os
from collections import defaultdict, deque
from typing import Callable

import hou
import pyblish

from ayon_houdini.api import lib
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext


import importlib

importlib.reload(lib)


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
    # filter out the increment plugin because it will cause our export to get out of sync with later run nodes
    filtered_plugins = [
        plugin
        for plugin in pyblish_plugins
        if not "IncrementCurrentFile" in str(plugin)
    ]

    for result in pyblish.util.publish_iter(pyblish_context, filtered_plugins):

        log.debug(result)
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
    rop_node: hou.Node, log: logging.Logger, val: str
):
    node_list = [rop_node]
    node_list.extend(rop_node.inputAncestors())
    for node in node_list:

        if node.type() == hou.nodeType(
            hou.ropNodeTypeCategory(), "ynput::dev::ayon_publish::1.7"
        ):
            node.parm("prerender").set(val)


frame_var_regx = r"\$F(?:\d*|F)"


def get_rop_output(rop: hou.RopNode) -> list:
    """returns a list of output files a Given node will generated based on Frame range and replacement Varaibles

    Args:
        rop: input Rop Node



    Returns (list:str): list of strings with the output files. Empty list if its not possible to evaluate the output

    """
    out_parm = lib.get_output_parameter(rop)
    rop = out_parm.node()

    renders_range = rop.parm("trange").eval()

    if 0 == renders_range:  # Render Current Frame
        return [out_parm.eval()]
        # just evaluate the parm
    elif (
        1 == renders_range or 2 == renders_range
    ):  # Render Frame Range or Render Frame Range Only
        raw_out = out_parm.rawValue()

        match = re.findall(frame_var_regx, raw_out)
        if not match:
            # if no Range parms exist we just return the eveluated parm
            return [out_parm.eval()]

        start = rop.parm("f1").eval()
        end = rop.parm("f2").eval()
        inc = rop.parm("f3").eval()
        out_list = []
        # TODO dose this need to be O(n*m) ?

        # TODO find out why expandString replaces $OS with Director and not the actual node name
        # https://www.sidefx.com/docs/houdini/network/expressions.html#globals
        os_replaced_out = raw_out.replace("$OS", rop.name())
        for frame in range(int(start), int(end), int(inc)):
            frame_out_parm = os_replaced_out

            # TODO this dose not handle the different frame padding options correctly
            for i in match:
                num = re.findall(r"\d+", i)[0]
                frame_out_parm = frame_out_parm.replace(i, str(frame).zfill(int(num)))

            frame_out_parm = hou.expandString(frame_out_parm)
            if not os.path.exists(
                frame_out_parm
            ):  # TODO this should probably check the time stamp to avoid publishing files from old exports into the same dir
                continue
            out_list.append(frame_out_parm)

        return out_list

    return []


def ayon_publish_command():
    """This command is called by the AYON Publish Rop and will trigger
    publish only for this given node."""
    publish(hou.pwd().path())
