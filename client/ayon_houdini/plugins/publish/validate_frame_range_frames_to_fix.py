# -*- coding: utf-8 -*-
import clique

import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateFrameRangeFramesToFix(plugin.HoudiniInstancePlugin):
    """Validate Frame Range Frames to Fix.

    This validator checks if the rop node covers the entire frame 
    range, including any frames that require correction.
    It also verifies the absence of gaps within the specified frames to fix.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range Frames to Fix"
    actions = [SelectROPAction]

    def process(self, instance):

        if not instance.data.get("instance_node"):
            return

        frames_to_fix: str = instance.data.get("frames_to_fix", "")
        if not frames_to_fix:
            self.log.debug("Skipping Validation, no frames to fix.")
            return

        # Skip instances that are set to not be integrated so we ignore
        # the original `render` instance from which local AOV instances are
        # spawned off.
        if not instance.data.get("integrate", True):
            return

        frame_start = instance.data["frameStartHandle"]
        frame_end = instance.data["frameEndHandle"]

        # Get the frame range from 'frames to fix'
        try:
            collection = clique.parse(frames_to_fix, "{ranges}")
        except ValueError:
            # Invalid frame pattern entered
            raise PublishValidationError(
                f"Invalid frames to fix pattern: '{frames_to_fix}'",
                description=(
                    "The frames to fix pattern specified is invalid. It must "
                    "be of the form `5,10-15`.\n\n"
                    "The pattern must be a comma-separated list of frames or "
                    "frame ranges. A frame is a whole number, like `5`, and a "
                    "frame range is two whole numbers separated by a hyphen, "
                    "like `5-10` indicating the frames `5,6,7,8,9,10`."
                )
            )

        fix_frames: "list[int]" = list(collection)
        fix_frame_start = int(fix_frames[0])
        fix_frame_end = int(fix_frames[-1])

        # Check if ROP frame range covers the frames to fix.
        # Title and message are the same for the next two checks.
        invalid_range = False
        if frame_start > fix_frame_start:
            self.log.error(
                "Start frame should be smaller than or equal to the first "
                "frame to fix. Set the start frame to the first frame to fix: "
                f"{fix_frame_start}."
            )
            invalid_range = True

        if frame_end < fix_frame_end:
            self.log.error(
                "End frame should be greater than or equal to the last frame "
                "to fix. Set the end frame to the last frame to fix: "
                f"{fix_frame_end}."
            )
            invalid_range = True
            
        if invalid_range:
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
