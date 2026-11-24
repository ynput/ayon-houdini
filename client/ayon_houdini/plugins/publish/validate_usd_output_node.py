# -*- coding: utf-8 -*-
import inspect

import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateUSDOutputNode(plugin.HoudiniInstancePlugin):
    """Validate the instance USD LOPs Output Node.

    This will ensure:
        - The LOP Path is set.
        - The LOP Path refers to an existing object.
        - The LOP Path node is a LOP node.

    """

    # Validate early so that this error reports higher than others to the user
    # so that if another invalidation is due to the output node being invalid
    # the user will likely first focus on this first issue
    order = pyblish.api.ValidatorOrder - 0.4
    families = ["usdrop"]
    label = "Validate Output Node (USD)"
    actions = [SelectROPAction]

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            node_path = invalid[0].path()
            raise PublishValidationError(
                f"Output node '{node_path}' has no valid LOP path set.",
                title=self.label,
                description=self.get_description()
            )

    @classmethod
    def get_invalid(cls, instance):

        import hou

        output_node = instance.data.get("output_node")

        if output_node is None:
            node = hou.node(instance.data.get("instance_node"))
            cls.log.error(
                f"USD node '{node.path()}' has no valid LOP path set."
            )
            return [node]

        # Output node must be a LOP node.
        if not isinstance(output_node, hou.LopNode):
            node_type = output_node.type()
            category = node_type.category().name()
            label = node_type.description() if category == "Lop" else category
            cls.log.error(
                f"LOP path '{output_node.path()}' ({label}) does not "
                "output a USD stage. Point it to a Solaris LOP node "
                "instead."
            )
            return [output_node]

    def get_description(self):
        return inspect.cleandoc(
            """### USD ROP has invalid LOP path

            The USD ROP node has an invalid LOP path set to be exported.
            The LOP path must point to an existing LOP (Solaris) node.

            To export SOP geometry, import it into Solaris first (e.g.
            with a SOP Import LOP) and point the LOP path to that.

            Make sure to correctly configure what you want to export for the
            publish.
            """
        )
