# -*- coding: utf-8 -*-
import pyblish.api

from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import plugin


class ValidateIntermediateDirectoriesChecked(plugin.HoudiniInstancePlugin):
    """Validate Create Intermediate Directories is enabled on ROP node."""

    order = pyblish.api.ValidatorOrder
    families = ["pointcache", "camera", "vdbcache", "model"]
    label = "Create Intermediate Directories Checked"

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            nodes = "\n".join(f"- {node.path()}" for node in invalid)
            raise PublishValidationError(
                ("Found ROP node with Create Intermediate "
                 "Directories turned off:\n {}".format(nodes)),
                title=self.label)

    @classmethod
    def get_invalid(cls, instance):

        result = []

        for node in instance[:]:
            if node.parm("mkpath").eval() != 1:
                cls.log.error("Invalid settings found on `%s`" % node.path())
                result.append(node)

        return result
