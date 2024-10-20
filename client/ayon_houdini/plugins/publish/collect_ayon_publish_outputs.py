import os

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
    families = ["pub"]

    def process(self, instance):

        # Get the AYON Publish ROP node and the input ROPs we want to collect
        # as part of this instance.
        rop_node = hou.node(instance.data["instance_node"])
        input_rops = ayon_publish.get_input_rops(rop_node)

        self.log.debug(
            f"Collecting '{rop_node.path()} input ROPs: {input_rops}")

        representations = instance.data.setdefault("representations", [])
        for input_rop in input_rops:

            try:
                file_parm = lib.get_output_parameter(input_rop)
            except TypeError:
                self.log.warning(
                    f"Skipping unsupported ROP type '{input_rop.path()}' as "
                    "we can not detect its output files.")
                continue
            self.log.debug(f"Processing: '{input_rop.path()}'")

            # TODO: Support filepaths with frame ranges, like $F4
            filepath = file_parm.eval()

            # Split extension, but allow for multi-dot extensions
            ext = lib.splitext(
                filepath,
                allowed_multidot_extensions=[
                ".ass.gz", ".bgeo.sc", ".bgeo.gz",
                ".bgeo.lzma", ".bgeo.bz2"]
            )[-1]
            ext_no_dot = ext[1:]

            representation = {
                "name": ext_no_dot,
                "ext": ext_no_dot,
                "files": os.path.basename(filepath),
                "stagingDir": os.path.dirname(filepath),
            }
            self.log.debug(f"Collected representation: {representation}")
            representations.append(representation)