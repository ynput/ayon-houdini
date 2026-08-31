import hou

import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction
from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectInvalidAction


class FixParameterAction(RepairAction):
    label = "Add $F4 to 'lopoutput'"


class ValidateFrameTokenUSDRender(plugin.HoudiniInstancePlugin):
    """Validate if the unexpanded string contains the frame ('$F') token.

    This validator will *only* check the output parameter of the node if
    the "Use Custom Frames" attribute is set.

    Rules:
        If "Use Custom Frames" attribute is set in publisher
        it is mandatory to have the frame token - '$F4' or similar -
        to ensure that each frame gets written.
        If this is not the case you may face black render
        as the output USD file may not cover the whole range.

    Examples:
        Good: '__render__.$F4.usd'
        Bad: '__render__.usd'

    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Token (USD Render)"
    families = ["usdrender"]
    actions = [FixParameterAction, SelectInvalidAction]

    def process(self, instance):
        if not instance.data.get("farm"):
            self.log.debug("Not a farm instance, skipping.")
            return

        if "deadline.submit.publish.job" not in instance.data["families"]:
            self.log.debug(
                "Should only checked if submitting to deadline, skipping.")
            return

        job_info = instance.data["deadline"]["job_info"]

        if job_info.Frames is None:
            self.log.debug(
                "Should only checked if deadline job has custom frames,"
                " skipping."
            )
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "No frame token found in the USD Export Output File parm in"
                f" '{invalid[0].path()}'"
            )

    @classmethod
    def get_invalid(cls, instance):

        node = hou.node(instance.data["instance_node"])
        output_parm = node.parm("lopoutput")
        unexpanded_str = output_parm.unexpandedString()

        if "$F" not in unexpanded_str:
            return [node]

    @classmethod
    def repair(cls, instance):
        if not cls.get_invalid(instance):
            # Already fixed
            return

        import os 

        rop_node = hou.node(instance.data["instance_node"])
        lopoutput = rop_node.parm("lopoutput").eval()
        path, ext = os.path.splitext(lopoutput)
        rop_node.parm("lopoutput").set(f"{path}.$F4{ext}")
