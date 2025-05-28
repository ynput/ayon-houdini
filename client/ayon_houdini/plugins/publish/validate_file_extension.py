# -*- coding: utf-8 -*-
import os
import hou

import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import lib, plugin


class ValidateFileExtension(plugin.HoudiniInstancePlugin):
    """Validate the output file extension fits the output product type.

    File extensions:
        - Pointcache must be .abc
        - Camera must be .abc
        - VDB must be .vdb

    """

    order = pyblish.api.ValidatorOrder
    families = ["camera", "vdbcache"]
    label = "Output File Extension"

    product_type_extensions = {
        "camera": ".abc",
        "vdbcache": ".vdb",
    }

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                f"ROP node has incorrect file extension: {invalid[0].path()}",
                title=self.label
            )

    @classmethod
    def get_invalid(cls, instance):
        # Get expected extension
        product_type = instance.data.get("productType")
        extension = cls.product_type_extensions.get(product_type, None)
        if extension is None:
            raise PublishValidationError(
                "Unsupported product type: {}".format(product_type),
                title=cls.label)

        # Perform extension check
        node = hou.node(instance.data["instance_node"])
        output = lib.get_output_parameter(node).eval()
        _, output_extension = os.path.splitext(output)
        if output_extension != extension:
            return [node]
