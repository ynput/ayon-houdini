# -*- coding: utf-8 -*-
import hou
import clique 

import pyblish.api
from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction

from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class UpdateSceneFrameRangeAction(RepairAction):
    label = "Update scene frame range by frames to fix"


class ValidateFrameRangeFramesToFix(plugin.HoudiniInstancePlugin):
    """Validate Frame Range Frames to Fix.

    This validator checks if the rop node covers the entire frame range, including any frames that require correction.
    It also verifies the absence of gaps within the specified frames to fix.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range Frames to Fix"
    actions = [UpdateSceneFrameRangeAction, SelectInvalidAction]

    def process(self, instance):

        invalid_nodes, title, message = self.get_invalid_with_message(instance)
        if invalid_nodes:
            raise PublishValidationError(
                title=title,
                message=message,
                description= f"## {title}\n{message}"
            )

    @classmethod
    def get_invalid(cls, instance):
        nodes, _, _ = cls.get_invalid_with_message(instance)
        return nodes
    
    @classmethod
    def get_invalid_with_message(cls, instance):

        if not instance.data.get("instance_node"):
            return

        rop_node = hou.node(instance.data["instance_node"])
        frame_start = instance.data.get("frameStartHandle") 
        frame_end = instance.data.get("frameEndHandle")

        frames_to_fix = instance.data.get("frames_to_fix", "")
        if not frames_to_fix:
            cls.log.debug("Skipping Validation, No frames to fix.")
            return (None, None)

        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")
        
        # Check if frames to fix include any gaps.
        if not frames_to_fix.is_contiguous():
            title = "Invalid Frames To Fix"
            message = (
                "Frames to fix [{0[frames_to_fix]}] include gaps.\n"
                "Please, use a value that has no gaps."
                .format(instance.data)
            )

            cls.log.error("Frames to fix include gaps.")
            return (rop_node.path(), title, message)

        # Check if ROP frame range covers the frames to fix.
        frame_range = list(frames_to_fix)
        # Title and message are the same for the next two checks.
        title = "Invalid Rop Frame Range"
        message = (
            "Invalid frame range because the instance "
            "frame range [{0[frameStart]} - {0[frameEnd]}] doesn't cover "
            "the frames to fix [{0[frames_to_fix]}]."
            .format(instance.data)
        )
        if not frame_start <= int(frame_range[0]):
            cls.log.error(
                "Start frame should be smaller than or equal the first frame to fix."
                f"Setting the start frame to the first frame to fix {int(frame_range[0])}."
            )
            return (rop_node.path(), title, message)

        if not frame_end >= int(frame_range[-1]):
            cls.log.error(
                "End frame should be greater than or equal the last frame to fix."
                f"Setting the end frame to the last frame to fix {int(frame_range[-1])}."
            )
            return (rop_node.path(), title, message)

    @classmethod
    def repair(cls, instance):

        if not cls.get_invalid(instance):
            # Already fixed
            return
        frames_to_fix = instance.data.get("frames_to_fix", "")
        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")
        frame_range = list(frames_to_fix)

        frame_start, frame_end = hou.playbar.frameRange()
        if not frame_start <= int(frame_range[0]):
            frame_start = int(frame_range[0])
        if not frame_end >= int(frame_range[-1]):
            frame_end = frame_range[-1]

        frame_start = int(frame_start)
        frame_end = int(frame_end)

        # Set frame range
        hou.playbar.setFrameRange(frame_start, frame_end)
        hou.playbar.setPlaybackRange(frame_start, frame_end)
        hou.setFrame(frame_start)