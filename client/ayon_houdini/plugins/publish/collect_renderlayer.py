"""Collect Render layer name from ROP.

This simple collector will take name of the ROP node and set it as the render
layer name for the instance.

This aligns with the behavior of Maya and possibly others, even though there
is nothing like render layer explicitly in Houdini.

"""
import hou
import pyblish.api
from ayon_houdini.api import plugin


class CollectRendelayerFromROP(plugin.HoudiniInstancePlugin):
    label = "Collect Render layer name from ROP"
    order = pyblish.api.CollectorOrder - 0.499
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender"]

    def process(self, instance):
        rop = hou.node(instance.data.get("instance_node"))
        instance.data["renderlayer"] = rop.name()
