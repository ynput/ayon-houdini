"""Validator for the inputs of an AYON Publish ROP."""
import hou
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api import plugin, ayon_publish


class ValidateAYONPublishInputs(plugin.HoudiniInstancePlugin):
    """Validate the input/dependency ROPs of an AYON Publish ROP.

    AYON Publish ROPs do not write output files themselves; they only trigger
    publishing. Using one as an input (or dependency) of another AYON Publish
    ROP would render a no-op driver and surface as Houdini's confusing
    ``Error rendering input: <node>`` message.
    """

    order = pyblish.api.ValidatorOrder
    families = ["rop_publish"]
    label = "Validate AYON Publish Inputs"

    def process(self, instance):
        rop_node = hou.node(instance.data["instance_node"])
        if rop_node is None:
            return

        nested_nodes = ayon_publish.get_nested_ayon_publish_nodes(rop_node)
        if not nested_nodes:
            return

        raise PublishValidationError(
            "The AYON Publish ROP depends on another AYON Publish ROP. "
            "AYON Publish ROPs do not write output files themselves, so they "
            "cannot be used as inputs or dependencies. Connect the native "
            "output ROP(s) directly instead.",
            title=self.label,
            detail="Nested AYON Publish ROPs:\n{}".format(
                "\n".join(f" - {node.path()}" for node in nested_nodes)
            ),
        )
