# -*- coding: utf-8 -*-
import inspect

import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction

from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class ValidateComponentBuilderLocalize(plugin.HoudiniInstancePlugin):
    """Validate Component Output localizes external non-USD files.

    With "Localize External Non-USD Files" turned off, textures stay
    outside the component folder and Houdini writes paths to them that
    don't survive publishing (relative `../` paths on the same drive,
    absolute paths on a different drive). Those files are not part of
    the published component.
    """

    order = pyblish.api.ValidatorOrder
    families = ["componentbuilder"]
    label = "Validate Component Builder Localize"
    actions = [SelectInvalidAction, RepairAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"Component Output '{invalid[0].path()}' has "
                "\"Localize External Non-USD Files\" turned off.",
                title=self.label,
                description=self.get_description()
            )

    @classmethod
    def get_invalid(cls, instance):
        node = hou.node(instance.data["instance_node"])
        if not node.evalParm("localize"):
            return [node]
        return []

    @classmethod
    def repair(cls, instance):
        node = hou.node(instance.data["instance_node"])
        node.parm("localize").set(True)

    @staticmethod
    def get_description():
        return inspect.cleandoc(
            """### Localize External Non-USD Files is off

            The Component Output node must have **Localize External
            Non-USD Files** turned on, so textures are copied into the
            component folder and published with it.

            Use the repair action to turn it on, then reset the publisher
            so the component is exported again.
            """
        )
