import pyblish.api
import ayon_api

from ayon_core.lib.attribute_definitions import (
    TextDef,
    BoolDef
)
from ayon_core.pipeline.publish import AYONPyblishPluginMixin

from ayon_houdini.api import plugin


class CollectFramesFixDefHou(
    plugin.HoudiniInstancePlugin,
    AYONPyblishPluginMixin
):
    """Provides text field to insert frame(s) to be re-rendered.

    Published files of last version of an instance product are collected into
    `instance.data["last_version_published_files"]`. All these but frames
    mentioned in text field will be reused for new version.
    """
    order = pyblish.api.CollectorOrder + 0.495
    label = "Collect Frames to Fix"
    targets = ["local"]
    families = ["*"]

    rewrite_version_enable = False

    def process(self, instance):
        attribute_values = self.get_attr_values_from_data(instance.data)
        frames_to_fix: str = attribute_values.get("frames_to_fix", "")
        rewrite_version: bool = (
            self.rewrite_version_enable
            and attribute_values.get("rewrite_version", False)
        )
        if not frames_to_fix:
            if rewrite_version:
                self.log.warning(
                    "Rewrite version is enabled but no frames to fix are "
                    "specified. Rewriting last version will be skipped.")
            return

        self.log.info(f"Frames to fix: {frames_to_fix}")
        instance.data["frames_to_fix"] = frames_to_fix

        # Skip instances that are set to not be integrated so we ignore
        # the original `render` instance from which local AOV instances are
        # spawned off.
        if not instance.data.get("integrate", True):
            self.log.debug("Skipping collecting frames to fix data for "
                           "instance because instance is set to not integrate")
            return

        product_name: str = instance.data["productName"]
        folder_entity: dict = instance.data["folderEntity"]
        project_entity: dict = instance.data["projectEntity"]
        project_name: str = project_entity["name"]

        product_entity = ayon_api.get_product_by_name(
            project_name,
            product_name,
            folder_id=folder_entity["id"])
        if not product_entity:
            self.log.warning(
                f"No existing product found for '{product_name}'. "
                "Re-render not possible."
            )
            return

        product_type = product_entity["productType"]
        instance_product_type = instance.data["productType"]
        if product_type != instance_product_type:
            self.log.error(
                f"Existing product '{product_name}' product type "
                f"'{product_type}' is not the same as instance product type "
                f"'{instance_product_type}'. Re-render may have unintended "
                f"side effects.")

        version_entity = ayon_api.get_last_version_by_product_id(
            project_name,
            product_id=product_entity["id"],
        )
        if not version_entity:
            self.log.warning(
                f"No last version found for product '{product_name}', "
                "re-render not possible."
            )
            return

        representations = ayon_api.get_representations(
            project_name, version_ids={version_entity["id"]}
        )

        # Get all published files for the representation
        published_files: "list[str]" = []
        for repre in representations:
            for file_info in repre.get("files"):
                published_files.append(file_info["path"])

        instance.data["last_version_published_files"] = published_files
        self.log.debug(f"last_version_published_files: {published_files}")

        if rewrite_version:
            instance.data["version"] = version_entity["version"]
            # limits triggering version validator
            instance.data.pop("latestVersion")

    @classmethod
    def get_attribute_defs(cls):
        attributes = [
            TextDef("frames_to_fix", label="Frames to fix",
                    placeholder="5,10-15",
                    regex="[0-9,-]+",
                    tooltip=(
                        "When specified, only these frames will be rendered.\n"
                        "The remainder of the frame range for the instance "
                        "will be copied from the previous published version.\n"
                        "This allows re-rendering only certain frames or "
                        "extending the frame range of the previous version.\n"
                        "The frames to fix must be inside the instance's "
                        "frame range.\n"
                        "Example: 5,10-15"
                    ))
        ]

        if cls.rewrite_version_enable:
            attributes.append(
                BoolDef(
                    "rewrite_version",
                    label="Rewrite latest version",
                    default=False,
                    tooltip=(
                        "When enabled the new version will be published into"
                        "the previous version and apply only the 'fixed "
                        "frames'.\n"
                        "**Note:** This does nothing if no Frames to Fix are "
                        "specified."
                    )
                )
            )

        return attributes
