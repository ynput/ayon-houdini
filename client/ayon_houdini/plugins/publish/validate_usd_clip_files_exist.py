# -*- coding: utf-8 -*-
import os
import inspect

import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class ValidateUSDClipFilesExist(plugin.HoudiniInstancePlugin):
    """Validate the clip files loaded by Geometry Clip Sequence nodes exist.

    When 'Get Geometry From Second Input' is disabled the Geometry Clip
    Sequence node loads existing clip files from 'Load Clip File Path'. Those
    files must exist for the frames in the ROP render range, otherwise the USD
    ROP fails to extract and the files can't be transferred to the publish.

    The loaded clip files are collected by `CollectUSDValueClips`.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usd"]
    label = "Validate USD Clip Files Exist"
    actions = [SelectInvalidAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            nodes = "\n".join(f"- {node.path()}" for node in invalid)
            raise PublishValidationError(
                f"Geometry Clip Sequence nodes have missing clip files:\n"
                f"{nodes}",
                title=self.label,
                description=self.get_description()
            )

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        loaded_clip_files = instance.data.get("usdLoadedClipFiles", {})
        for node_path, files in loaded_clip_files.items():
            missing = [path for path in files if not os.path.isfile(path)]
            if not missing:
                continue

            cls.log.error(
                f"Geometry Clip Sequence '{node_path}' is missing "
                f"{len(missing)} clip files from 'Load Clip File Path':\n"
                + "\n".join(missing)
            )
            invalid.append(hou.node(node_path))

        return invalid

    def get_description(self):
        return inspect.cleandoc(
            """### Missing clip files

            Geometry Clip Sequence nodes with **Get Geometry From Second
            Input** disabled load existing clip files from **Load Clip File
            Path**. Those files must exist for all clip frames within the
            publish frame range, otherwise the USD ROP will fail.

            Make sure the clip files are written out first, or adjust the
            clip's start and end frame or the publish frame range. See the
            log for the list of missing files.
            """
        )
