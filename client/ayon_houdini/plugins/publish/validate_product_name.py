# -*- coding: utf-8 -*-
"""Validator for correct naming of Static Meshes."""
import hou

from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_core.pipeline.publish import (
    ValidateContentsOrder,
    RepairAction,
)
from ayon_core.pipeline.create import get_product_name
from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectInvalidAction


class FixProductNameAction(RepairAction):
    label = "Fix Product Name"


class ValidateProductName(plugin.HoudiniInstancePlugin,
                          OptionalPyblishPluginMixin):
    """Validate Product name."""

    families = ["staticMesh", "hda"]
    label = "Validate Product Name"
    order = ValidateContentsOrder + 0.1
    actions = [FixProductNameAction, SelectInvalidAction]

    optional = True

    def process(self, instance):

        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "See log for details. "
                "Invalid ROP node: {0}".format(invalid[0].path())
            )

    @classmethod
    def get_invalid(cls, instance):

        rop_node = hou.node(instance.data["instance_node"])

        # Check product name
        folder_entity = instance.data["folderEntity"]
        task_entity = instance.data["taskEntity"]
        task_name = task_type = None
        if task_entity:
            task_name = task_entity["name"]
            task_type = task_entity["taskType"]
        product_name = get_product_name(
            instance.context.data["projectName"],
            task_name,
            task_type,
            instance.context.data["hostName"],
            instance.data["productType"],
            variant=instance.data["variant"],
            dynamic_data={
                "folder": {
                    "label": folder_entity["label"],
                    "name": folder_entity["name"],
                },
                # Backwards compatibility
                "asset": folder_entity["name"],
            },
        )

        if instance.data.get("productName") != product_name:
            cls.log.error(
                "Invalid product name on rop node '%s' should be '%s'.",
                rop_node.path(), product_name
            )
            return [rop_node]

    @classmethod
    def repair(cls, instance):
        rop_node = hou.node(instance.data["instance_node"])

        # Check product name
        folder_entity = instance.data["folderEntity"]
        task_entity = instance.data["taskEntity"]
        task_name = task_type = None
        if task_entity:
            task_name = task_entity["name"]
            task_type = task_entity["taskType"]
        product_name = get_product_name(
            instance.context.data["projectName"],
            task_name,
            task_type,
            instance.context.data["hostName"],
            instance.data["productType"],
            variant=instance.data["variant"],
            dynamic_data={
                "asset": folder_entity["name"],
                "folder": {
                            "label": folder_entity["label"],
                            "name": folder_entity["name"]
                            }
                }
        )

        instance.data["productName"] = product_name
        rop_node.parm("AYON_productName").set(product_name)

        cls.log.debug(
            "Product name on rop node '%s' has been set to '%s'.",
            rop_node.path(), product_name
        )

    @classmethod
    def convert_attribute_values(
        cls, create_context, instance
    ):
        # Convert old class name `ValidateSubsetName` to new class name
        # `ValidateProductName` in the instance data.
        if not instance:
            return

        publish_attributes = instance.data.get("publish_attributes", {})
        if not publish_attributes:
            return

        if (
                "ValidateSubsetName" in publish_attributes
                and "ValidateProductName" not in publish_attributes
        ):
            cls.log.debug(
                "Converted `ValidateSubsetName` -> `ValidateProductName` "
                f"in publish attributes for {instance['productName']}"
            )

            # Until PR https://github.com/ynput/ayon-core/pull/1219 we can't
            # use `publish_attributes` directly. We can't `pop()` the key
            # either. Use this logic as soon as `ayon-houdini` requires an
            # `ayon-core` version with the fix included.
            # publish_attributes["ValidateProductName"] = (
            #     publish_attributes.pop("ValidateSubsetName")
            # )
            publish_attributes._data["ValidateProductName"] =(
                publish_attributes["ValidateSubsetName"]
            )
