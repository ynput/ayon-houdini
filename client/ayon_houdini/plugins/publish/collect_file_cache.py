# -*- coding: utf-8 -*-
"""Collect the cache files and frame range for AYON File Cache instances."""
import os

import hou
import pyblish.api

from ayon_core.pipeline.publish import PublishError
from ayon_houdini.api import plugin


class CollectFileCache(plugin.HoudiniInstancePlugin):
    """Collect the AYON File Cache output files for publishing."""

    order = pyblish.api.CollectorOrder + 0.2
    families = ["filecache"]
    label = "Collect File Cache"
    targets = ["local"]

    def process(self, instance):
        node = hou.node(instance.data.get("instance_node"))
        if node is None:
            raise PublishError(
                "AYON File Cache instance node no longer exists."
            )

        # Instance data from a reloaded scene may only have the namespaced
        # copies because folderPath/task are HDA definition parameters.
        instance.data.setdefault(
            "folderPath",
            instance.data.get("AYON_CACHE_FOLDER_PATH")
            or node.evalParm("folderPath"),
        )
        instance.data.setdefault(
            "task",
            instance.data.get("AYON_CACHE_TASK")
            or node.evalParm("task"),
        )

        outputs = self._expected_outputs(node)
        if not outputs:
            raise PublishError(
                "Could not resolve any expected cache files. "
                "Check the frame range and Save to Disk first."
            )

        cache_dir = os.path.dirname(outputs[0]).replace("\\", "/")
        names = [os.path.basename(path) for path in outputs]
        missing = [
            path for path in outputs if not os.path.isfile(path)
        ]
        if missing:
            raise PublishError(
                "The cache is incomplete. Missing output files:\n- "
                + "\n- ".join(missing)
            )

        frame_start, frame_end = self._frame_range(node)
        instance.data.update({
            "cacheDir": cache_dir,
            "frames": names,
            "stagingDir": cache_dir,
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "frameStartHandle": frame_start,
            "frameEndHandle": frame_end,
        })

        self.log.debug(
            "Collected %d cache file(s) from %s", len(names), cache_dir
        )

    @staticmethod
    def _expected_outputs(node):
        cache = node.node("filecache1")
        if cache is None:
            raise PublishError("Inner File Cache node was not found.")

        output_parm = cache.parm("sopoutput")
        frame_start, frame_end = CollectFileCache._frame_range(node)
        trange = node.evalParm("trange")
        substeps = max(1, int(node.evalParm("substeps")))
        frame_step = float(node.evalParm("f3"))

        if trange:
            frames = []
            frame = frame_start
            while frame <= frame_end + 1e-6:
                frames.append(frame)
                frame += frame_step / substeps
        else:
            if node.evalParm("useframeoverride"):
                frames = [float(node.evalParm("frameoverride"))]
            else:
                frames = [float(hou.frame())]

        outputs = []
        for frame in frames:
            path = output_parm.evalAtFrame(frame)
            path = hou.expandString(path)
            if path and path not in outputs:
                outputs.append(path)
        return outputs

    @staticmethod
    def _frame_range(node):
        if not node.evalParm("trange"):
            if node.evalParm("useframeoverride"):
                frame = int(node.evalParm("frameoverride"))
            else:
                frame = int(hou.frame())
            return frame, frame

        start = int(node.evalParm("f1"))
        end = int(node.evalParm("f2"))
        if end < start:
            end = start
        return start, end
