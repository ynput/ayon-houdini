import copy
import os
import re

import pyblish.api

from ayon_core.pipeline.create import get_product_name
from ayon_houdini.api import plugin, ayon_publish
import ayon_houdini.api.usd as usdlib

import hou


class CollectAyonPub(plugin.HoudiniInstancePlugin):
    """Collect Ayon Pub"""

    order = pyblish.api.CollectorOrder
    label = "Collect Ayon Pub"
    families = ["pub"]

    def process(self, instance):
        import importlib

        importlib.reload(ayon_publish)

        rop_node = hou.node(instance.data["instance_node"])
        out_con = rop_node.outputConnections()
        if out_con:
            self.log.debug("deactivate node")
            self.log.debug(instance.data)

        if not rop_node.parm("pub_from_node").eval():
            ayon_publish.set_ayon_publish_nodes_pre_render_script(
                rop_node, self.log, ""
            )
            rop_node.render()
            ayon_publish.set_ayon_publish_nodes_pre_render_script(
                rop_node, self.log, "hou.phm().run()"
            )

        parent_nodes = ayon_publish.get_us_node_graph(rop_node)

        self.log.debug(ayon_publish.get_graph_output(parent_nodes))
        for path in ayon_publish.get_graph_output(parent_nodes):

            representation = {
                "name": "".join(os.path.basename(path).split(".")[0:2]),
                "ext": os.path.splitext(os.path.basename(path))[-1][1:],
                "files": os.path.basename(path),
                "stagingDir": os.path.dirname(path),
            }
            instance.data["representations"].append(representation)
        self.log.debug(instance.data["representations"])
