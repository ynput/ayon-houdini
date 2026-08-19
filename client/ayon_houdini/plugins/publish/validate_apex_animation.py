# -*- coding: utf-8 -*-
import hou

import pyblish.api
from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction
from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class IsolateAnimation(RepairAction):
    label = "Isolate Animation"

class ValidateAPEXAnim(plugin.HoudiniInstancePlugin):
    """Validate output node has animation APEX data.

    Check if packed prim files match only "/animation".
    This is crucial to prevent any issue when loading the animation.
    """
    # Should run after ValidateSopOutputNode
    order = pyblish.api.ValidatorOrder + 0.1
    families = ["anim"]
    label = "Validate APEX Animation"
    actions = [SelectInvalidAction, IsolateAnimation]

    def process(self, instance):

        if not instance.data.get("instance_node"):
            # Ignore instances without an instance node
            # e.g. in memory bootstrap instances
            self.log.debug(
                "Skipping instance without instance node: {}".format(instance)
            )
            return

        invalid_nodes, message = self.get_invalid_with_message(instance)
        if invalid_nodes:
            raise PublishValidationError(
                message,
                title=self.label
            )

    @classmethod
    def get_invalid_with_message(cls, instance):

        output_node = instance.data.get("output_node")

        geo = output_node.geometry()

        # TODO: Check if this is a bgeo scene.
        # Same as the error in the Rig Tree
        # Invalid Hierarchy: No valid roots found, possible closed polygon

        anim_paths = set(geo.extractPackedPaths('/anim**'))
        if not anim_paths:
            error = (
                f"Output SOP node '{output_node}' doesn't"
                " have 'animation' folder to export."
                " Please check your RigTree."
            )
            return [output_node, error]

        all_paths = set(geo.extractPackedPaths('/**')) - set("/")

        if all_paths != anim_paths:
            error = (
                f"Output SOP node '{output_node.path()}' should only"
                " have 'animation' folder in RigTree."
            )
            return [output_node, error]

        return [None, None]

    @classmethod
    def get_invalid(cls, instance):
        node, _ = cls.get_invalid_with_message(instance)
        return [node]

    @classmethod
    def repair(cls, instance):
        """Isolate Animation Action.

        It is a helper action more than a repair action,
        used to add a default single value for the path.
        """

        output_node = instance.data.get("output_node")
        if cls.get_invalid(instance) != [output_node]:
            # Already solved or the error is not related to output node.
            return

        unpackfolder = output_node.parent().createNode(
            "unpackfolder", "AUTO_ISOLATE_ANIMATION")
        unpackfolder.parm("pattern").set("/animation")
        unpackfolder.parm("unpack").set(0)

        cls.log.debug(f"'{unpackfolder}' was created.")

        unpackfolder.setGenericFlag(hou.nodeFlag.DisplayComment, True)
        unpackfolder.setComment(
            "Isolate animation data keeping only 'animation' folder in RigTree"
        )

        if output_node.type().name() in ["null", "output"]:
            # Connect before
            unpackfolder.setFirstInput(output_node.input(0))
            unpackfolder.moveToGoodPosition()
            output_node.setFirstInput(unpackfolder)
            output_node.moveToGoodPosition()
        else:
            # Connect after
            unpackfolder.setFirstInput(output_node)

            rop_node = hou.node(instance.data["instance_node"])
            rop_node.parm("sop_path").set(unpackfolder.path())
            unpackfolder.moveToGoodPosition()

            cls.log.debug(
                f"SOP path on '{rop_node}' updated to new "
                f"output node '{unpackfolder}'"
            )
