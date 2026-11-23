# -*- coding: utf-8 -*-
"""Extract AYON File Cache files into a publishable representation."""
import os
import shutil
import tempfile

import pyblish.api

from ayon_core.pipeline import publish
from ayon_houdini.api import plugin


class ExtractFileCache(plugin.HoudiniExtractorPlugin):
    """Copy cache files to staging and create a cache representation."""

    order = pyblish.api.ExtractorOrder
    families = ["filecache"]
    label = "Extract File Cache"
    targets = ["local"]

    def process(self, instance):
        cache_dir = instance.data["cacheDir"]
        files = instance.data["frames"]
        if isinstance(files, str):
            files = [files]

        staging_dir = instance.data.get("stagingDir")
        copied_files = []
        for name in files:
            source = os.path.join(cache_dir, name)
            target = os.path.join(staging_dir, name)
            shutil.copy2(source, target)
            copied_files.append(name)

        first_name = copied_files[0]
        if first_name.endswith(".bgeo.sc"):
            extension = "bgeo.sc"
        else:
            extension = os.path.splitext(first_name)[-1].lstrip(".") or "bgeo"

        representation = {
            "name": extension,
            "ext": extension,
            "files": copied_files,
            "stagingDir": staging_dir,
            "frameStart": instance.data.get("frameStart"),
            "frameEnd": instance.data.get("frameEnd"),
        }
        instance.data.setdefault("representations", []).append(representation)

        self.log.debug(
            "Extracted %d cache file(s) to %s",
            len(copied_files),
            staging_dir,
        )
