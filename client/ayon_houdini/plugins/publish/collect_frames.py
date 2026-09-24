# -*- coding: utf-8 -*-
"""Collector plugin for frames data on ROP instances."""
from __future__ import annotations

import os
import typing

import hou  # noqa
import pyblish.api
from ayon_houdini.api import lib, plugin

if typing.TYPE_CHECKING:
    import logging


def float_range(start: float, end: float, step: float):
    """Simple float range generator."""
    if step == 0:
        raise ValueError("step must be non-zero")

    num_steps = int((end - start) / step)
    if num_steps < 0:
        return []
    return [start + i * step for i in range(num_steps + 1)]


class CollectFrames(plugin.HoudiniInstancePlugin):
    """Collect all frames which would be saved from the ROP nodes"""

    # This specific order value is used so that
    # this plugin runs after CollectRopFrameRange
    order = pyblish.api.CollectorOrder + 0.1
    label = "Collect Frames"
    families = ["camera", "vdbcache", "imagesequence", "ass",
                "redshiftproxy", "review", "pointcache", "fbx",
                "model", "bgeo", "image_rop"]

    log: logging.Logger

    def process(self, instance: pyblish.api.Instance):

        # CollectRopFrameRange computes `start_frame` and `end_frame`
        #  depending on the trange value.
        start_frame = instance.data["frameStartHandle"]
        end_frame = instance.data["frameEndHandle"]
        frame_step = instance.data.get("byFrameStep", 1.0)

        # Evaluate the file name at the first frame.
        ropnode = hou.node(instance.data["instance_node"])
        parm: hou.Parm = lib.get_output_parameter(ropnode)

        if start_frame != end_frame and parm.isTimeDependent():

            if frame_step % 1.0 == 0:
                frames = range(start_frame, end_frame+1)
            else:
                frames = float_range(start_frame, end_frame, frame_step)

            files = [parm.evalAtFrame(frame) for frame in frames]
            staging_dir = os.path.basename(files[0])
        else:
            files = parm.evalAtFrame(start_frame)
            staging_dir = os.path.basename(files)

        self.log.debug(f"Collected Frames: {files}")
        instance.data.update({
            "frames": files,
            "stagingDir": staging_dir
        })
