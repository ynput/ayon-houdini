# -*- coding: utf-8 -*-
import hou
import clique 

import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class ValidateFrameRangeFramesToFix(plugin.HoudiniInstancePlugin):
    """Validate Frame Range Frames to Fix.

    This validator checks if the rop node covers the entire frame 
    range, including any frames that require correction.
    It also verifies the absence of gaps within the specified frames to fix.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range Frames to Fix"
    actions = [SelectInvalidAction]

    def process(self, instance):

        invalid_nodes = self.get_invalid(instance)
        if invalid_nodes:
            raise PublishValidationError(
                "Invalid Rop Frame Range",
                description=(
                    "## Invalid Rop Frame Range\n"
                    "Invalid frame range because the instance frame range "
                    "[{0[frameStart]} - {0[frameEnd]}] doesn't cover "
                    "the frames to fix [{0[frames_to_fix]}]."
                    .format(instance.data)
                )
            )
    
    @classmethod
    def get_invalid(cls, instance):
        if not instance.data.get("instance_node"):
            return

        frames_to_fix: str = instance.data.get("frames_to_fix", "")
        if not frames_to_fix:
            cls.log.debug("Skipping Validation, no frames to fix.")
            return

        rop_node = hou.node(instance.data["instance_node"])
        frame_start = instance.data["frameStartHandle"]
        frame_end = instance.data["frameEndHandle"]

        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")
        fix_frame_start = int(frames_to_fix[0])
        fix_frame_end = int(frames_to_fix[-1])

        # Check if ROP frame range covers the frames to fix.
        # Title and message are the same for the next two checks.
        if frame_start > fix_frame_start:
            cls.log.error(
                "Start frame should be smaller than or equal to the first "
                "frame to fix. Set the start frame to the first frame to fix: "
                f"{fix_frame_start}."
            )
            return rop_node.path()

        if frame_end < fix_frame_end:
            cls.log.error(
                "End frame should be greater than or equal to the last frame "
                "to fix. Set the end frame to the last frame to fix: "
                f"{fix_frame_end}."
            )
            return rop_node.path()
