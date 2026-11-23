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

        cache_dir = self._get_cache_dir(node)
        if not cache_dir or not os.path.isdir(cache_dir):
            raise PublishError(
                "AYON File Cache output folder does not exist: "
                f"{cache_dir}"
            )

        files = sorted(
            name for name in os.listdir(cache_dir)
            if name.endswith((".bgeo.sc", ".bgeo", ".vdb"))
        )
        if not files:
            raise PublishError(
                "No cache files were found. Click Save to Disk first.\n"
                f"Cache folder: {cache_dir}"
            )

        frame_start = int(node.evalParm("f1"))
        frame_end = int(node.evalParm("f2"))
        if frame_end < frame_start:
            frame_end = frame_start

        instance.data.update({
            "cacheDir": cache_dir,
            "frames": files,
            "stagingDir": cache_dir,
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "frameStartHandle": frame_start,
            "frameEndHandle": frame_end,
        })

        self.log.debug(
            "Collected %d cache file(s) from %s", len(files), cache_dir
        )

    @staticmethod
    def _get_cache_dir(node):
        if node.evalParm("filemethod"):
            filepath = hou.expandString(node.evalParm("geometryFile"))
            return os.path.dirname(filepath) if filepath else None

        resolved = node.evalParm("resolvedPath")
        if resolved:
            return hou.expandString(resolved)

        # Fallback for older cached HDA definitions.
        cache_root = hou.expandString(node.evalParm("cacheRoot"))
        folder = hou.expandString(node.evalParm("folderPath")).lstrip("/\\")
        task = hou.expandString(node.evalParm("task"))
        name = hou.expandString(node.evalParm("cacheName"))
        version = int(node.evalParm("version"))
        return os.path.join(
            cache_root, folder, task, name, "v%03d" % version
        )

