import hou

import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api import lib, plugin


class ValidateFrameToken(plugin.HoudiniInstancePlugin):
    """Validate if the unexpanded string contains the frame ('$F') token.

    This validator will *only* check the output parameter of the node if
    the Valid Frame Range is not set to 'Render Current Frame'

    Rules:
        If you render out a frame range it is mandatory to have the
        frame token - '$F4' or similar - to ensure that each frame gets
        written. If this is not the case you will override the same file
        every time a frame is written out.

    Examples:
        Good: 'my_vbd_cache.$F4.vdb'
        Bad: 'my_vbd_cache.vdb'

    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Token"
    families = ["vdbcache"]

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "Output settings do no match for '%s'" % instance
            )

    @classmethod
    def get_invalid(cls, instance):

        node = hou.node(instance.data["instance_node"])
        # Check trange parm, 0 means Render Current Frame
        frame_range = node.evalParm("trange")
        if frame_range == 0:
            return

        output_parm = lib.get_output_parameter(node)
        unexpanded_str = output_parm.unexpandedString()

        if "$F" not in unexpanded_str:
            cls.log.error("No frame token found in '%s'" % node.path())
            return [node]
