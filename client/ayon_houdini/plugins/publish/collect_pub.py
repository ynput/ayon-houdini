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

        rop_node = hou.node(instance.data["instance_node"])
        import importlib

        importlib.reload(ayon_publish)

        parent_nodes = ayon_publish.get_us_node_graph(rop_node)
        t = ayon_publish.print_grapth(parent_nodes)

        self.log.debug("\n" + t)

        self.log.debug(ayon_publish.get_graph_output(parent_nodes))
        for path in ayon_publish.get_graph_output(parent_nodes):

            representation = {
                "name": "".join(os.path.basename(path).split(".")[0:2]),
                "ext": os.path.splitext(os.path.basename(path))[-1][1:],
                "files": os.path.basename(path),
                "stagingDir": os.path.dirname(path),
            }
            self.log.debug(representation)
            instance.data["representations"].append(representation)
        self.log.debug(instance.data["representations"])
