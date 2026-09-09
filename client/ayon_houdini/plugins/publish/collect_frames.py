# -*- coding: utf-8 -*-
"""Collector plugin for frames data on ROP instances."""
import os
import re
import hou  # noqa
import pyblish.api
from ayon_houdini.api import lib, plugin


class CollectFrames(plugin.HoudiniInstancePlugin):
    """Collect all frames which would be saved from the ROP nodes"""

    # This specific order value is used so that
    # this plugin runs after CollectRopFrameRange
    order = pyblish.api.CollectorOrder + 0.1
    label = "Collect Frames"
    families = ["camera", "vdbcache", "imagesequence", "ass",
                "redshiftproxy", "review", "pointcache", "fbx",
                "model", "bgeo", "image_rop"]

    def process(self, instance):

        # CollectRopFrameRange computes `start_frame` and `end_frame`
        #  depending on the trange value.
        start_frame = instance.data["frameStartHandle"]
        end_frame = instance.data["frameEndHandle"]

        # Evaluate the file name at the first frame.
        ropnode = hou.node(instance.data["instance_node"])
        output_parm = lib.get_output_parameter(ropnode)
        output = lib.evalParmNoFrame(ropnode, output_parm.name())
        file_name = os.path.basename(output)

        # todo: `frames` currently conflicts with "explicit frames" for a
        #       for a custom frame list. So this should be refactored.

        frames = self.compute_frames(file_name, start_frame, end_frame)
        self.log.debug(f"Collected Frames: {frames}")

        instance.data.update({
            "frames": frames,
            "stagingDir": os.path.dirname(output)
        })

    def compute_frames(self, file_name, start, end):
            """Compute output frames.

            Args:
                file_name (str): Input file path containing hash tokens.
                start (int): Start frame.
                end (int): End frame.

            Returns:
                str | list[str]: A single frame path or a list of frame paths.
            """

            if "#" in file_name:
                def replace(match):
                    return "%0{}d".format(len(match.group()))

                file_name = re.sub("#+", replace, file_name)

            if "%" not in file_name:
                return file_name

            files = []
            for i in range(int(start), (int(end) + 1)):
                files.append(file_name % i)

            return files
