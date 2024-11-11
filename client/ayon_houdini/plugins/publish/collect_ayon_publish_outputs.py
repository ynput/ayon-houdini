import os
from re import findall

import pyblish.api

from ayon_houdini.api import lib, plugin, ayon_publish

import hou

# TODO: Remove this live debugging reload
import importlib

importlib.reload(ayon_publish)


class CollectAYONPublishOutputs(plugin.HoudiniInstancePlugin):
    """Collect output representations for AYON Publish node"""

    order = pyblish.api.CollectorOrder
    label = "Collect AYON Publish ROP outputs"
    families = ["rop_publish"]

    def process(self, instance):

        # Get the AYON Publish ROP node and the input ROPs we want to collect
        # as part of this instance.
        rop_node: hou.RopNode = hou.node(instance.data["instance_node"])
        if not instance.data.get("from_node", False):
            ayon_publish.set_ayon_publish_nodes_pre_render_script(
                rop_node,
                self.log,
                "",
            )
            try:
                rop_node.render()
            finally:
                ayon_publish.set_ayon_publish_nodes_pre_render_script(
                    rop_node,
                    self.log,
                    "hou.phm().run()",
                )

        input_rops = rop_node.inputs()
        self.log.debug(f"Collecting '{rop_node.path()} input ROPs: {input_rops}")

        representations = instance.data.setdefault("representations", [])
        for input_rop in input_rops:

            self.log.debug(f"Processing: '{input_rop.path()}'")

            try:
                file_parms = ayon_publish.get_rop_output(input_rop)
            except TypeError:
                self.log.warning(
                    f"Skipping unsupported ROP type '{input_rop.path()}' as "
                    "we can not detect its output files."
                )
                continue

            # TODO: Support filepaths with frame ranges, like $F4
            file_name_list = []
            for file in file_parms:
                file_name_list.append(os.path.basename(file))
                # Split extension, but allow for multi-dot extensions
            self.log.debug(f"files {file_parms}")
            ext = lib.splitext(
                file_parms[
                    0
                ],  # TODO this dose not work if first input is someting like merge or switch
                allowed_multidot_extensions=[
                    ".ass.gz",
                    ".bgeo.sc",
                    ".bgeo.gz",
                    ".bgeo.lzma",
                    ".bgeo.bz2",
                ],
            )[-1]
            ext_no_dot = ext[1:]

            if len(file_name_list) <= 1:
                self.log.debug(f"Single File Publish {file_name_list}")
                file_name_list = file_name_list[0]

            representation = {
                "name": ext_no_dot,
                "ext": ext_no_dot,
                "files": file_name_list,
                "stagingDir": os.path.dirname(file_parms[0]),
            }
            self.log.debug(f"Collected representation: {representation}")
            representations.append(representation)
