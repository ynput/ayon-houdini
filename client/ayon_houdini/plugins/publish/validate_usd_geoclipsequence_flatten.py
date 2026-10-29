# -*- coding: utf-8 -*-
import inspect

import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction
from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class ValidateUSDGeoClipSequenceFlatten(plugin.HoudiniInstancePlugin):
    """Validate Geometry Clip Sequence nodes using the second input flatten.

    With 'Get Geometry From Second Input' enabled and 'Flatten Clip Files'
    disabled the clip layers get saved to a location generated from the node
    path instead of 'Save Clip File Path', which makes the USD ROP fail.

    The Geometry Clip Sequence nodes are collected by `CollectUSDValueClips`.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usd"]
    label = "Validate USD Geometry Clip Sequence Flatten"
    actions = [SelectInvalidAction, RepairAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            nodes = "\n".join(f"- {node.path()}" for node in invalid)
            raise PublishValidationError(
                "Geometry Clip Sequence nodes get geometry from second input "
                f"but have 'Flatten Clip Files' disabled:\n{nodes}",
                title=self.label,
                description=self.get_description()
            )

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        for node_path in instance.data.get("usdGeoClipSequenceNodes", set()):
            node = hou.node(node_path)
            if (
                node.evalParm("usesecondinput")
                and not node.evalParm("flattenclips")
            ):
                cls.log.error(
                    f"Geometry Clip Sequence '{node_path}' has "
                    "'Get Geometry From Second Input' enabled but "
                    "'Flatten Clip Files' disabled."
                )
                invalid.append(node)

        return invalid

    @classmethod
    def repair(cls, instance):
        for node in cls.get_invalid(instance):
            node.parm("flattenclips").set(True)

    def get_description(self):
        return inspect.cleandoc(
            """### Geometry Clip Sequence clip files are not flattened

            Geometry Clip Sequence nodes with **Get Geometry From Second
            Input** enabled require **Flatten Clip Files** to be enabled.
            Otherwise the clip layers are saved to a location generated from
            the node path instead of **Save Clip File Path** and the USD ROP
            fails.

            Use the repair action to enable **Flatten Clip Files**.
            """
        )
