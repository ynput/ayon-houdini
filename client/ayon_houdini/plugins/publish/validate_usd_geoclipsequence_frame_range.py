# -*- coding: utf-8 -*-
import inspect

import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class ValidateUSDGeoClipSequenceFrameRange(plugin.HoudiniInstancePlugin):
    """Validate the publish frame range overlaps the Geometry Clip Sequence
    clip range.

    When the publish frame range ends before the clip start frame, or starts
    after the clip end frame (with 'Set End Frame' enabled and 'Loop Frames'
    disabled), the published layer only holds a single clip frame, so no clip
    animation is published. This is usually a leftover or wrong frame value.

    The Geometry Clip Sequence nodes are collected by `CollectUSDValueClips`.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usd"]
    label = "Validate USD Geometry Clip Sequence Frame Range"
    actions = [SelectInvalidAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            nodes = "\n".join(f"- {node.path()}" for node in invalid)
            raise PublishValidationError(
                "Geometry Clip Sequence clip ranges don't overlap the publish "
                f"frame range:\n{nodes}",
                title=self.label,
                description=self.get_description()
            )

    @classmethod
    def get_invalid(cls, instance):
        # Only the source USD ROP instance collects the clip nodes. Runtime
        # instances created during collection, like the save path layers and
        # the department and asset/shot contribution layers, have no clip
        # nodes and no frame range data.
        clip_nodes = instance.data.get("usdGeoClipSequenceNodes")
        if not clip_nodes:
            return []

        start = int(instance.data["frameStartHandle"])
        end = int(instance.data["frameEndHandle"])

        invalid = []
        for node_path in clip_nodes:
            node = hou.node(node_path)
            clip_start = int(node.evalParm("startframe"))
            clip_end = int(node.evalParm("endframe"))
            has_end = (
                node.evalParm("setendframe")
                and not node.evalParm("loopframes")
            )
            # Looping only repeats after the clip end, so a publish range
            # before the clip start is out of range in all cases.
            if end < clip_start or (has_end and start > clip_end):
                clip_range = f"{clip_start}-{clip_end if has_end else '...'}"
                cls.log.error(
                    f"Geometry Clip Sequence '{node_path}' clip range "
                    f"{clip_range} doesn't overlap the publish frame range "
                    f"{start}-{end}."
                )
                invalid.append(node)

        return invalid

    def get_description(self):
        return inspect.cleandoc(
            """### Clip range is out of the publish frame range

            The publish frame range doesn't overlap the clip range of the
            Geometry Clip Sequence nodes, so the published layer only holds
            a single clip frame for the whole frame range:

            - Before the clip: the clip **Start Frame**.
            - After the clip: the frame after the clip **End Frame**, when
              **Set End Frame** is enabled and **Loop Frames** is disabled.

            No clip animation is published. This is usually caused by a
            leftover or wrong value: check the clip **Start Frame** and
            **End Frame** and the publish frame range. See the log for the
            ranges of each node.
            """
        )
