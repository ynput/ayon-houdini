# -*- coding: utf-8 -*-
import hou

import pyblish.api
from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction

from ayon_houdini.api import plugin


class ValidateWaitForRender(plugin.HoudiniInstancePlugin):
    """Validate `WaitForRendertoComplete` is enabled.

    Disabling `WaitForRendertoComplete` cause the local render to fail
    as the publish execution continues while the render may not be finished yet.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    label = "Validate Wait For Render to Complete"
    actions = [RepairAction]

    def process(self, instance):

        if not instance.data.get("instance_node"):
            # Ignore instances without an instance node
            # e.g. in memory bootstrap instances
            self.log.debug(
                f"Skipping instance without instance node: {instance}"
            )
            return
        
        if instance.data["creator_attributes"].get("render_target") != "local":
            # This validator should work only with local render target.
            self.log.debug(
                "Skipping Validator, Render target is not 'Local machine rendering'"
            )
            return

        invalid = self.get_invalid(instance)
        if invalid:
            rop = invalid[0]
            raise PublishValidationError(
                ("ROP node '{}' has 'Wait For Render to Complete' parm disabled."
                 "Please, enable it.".format(rop.path())),
                title=self.label
            )

    @classmethod
    def get_invalid(cls, instance):

        rop = hou.node(instance.data["instance_node"])
        if not rop.evalParm("soho_foreground"):
            return [rop]
        
    @classmethod
    def repair(cls, instance):
        """Enable WaitForRendertoComplete. """

        rop = hou.node(instance.data["instance_node"])
        rop.parm("soho_foreground").set(True)

