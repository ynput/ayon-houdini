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
    """Provides text field to insert frame(s) to be rerendered.

    Published files of last version of an instance product are collected into
    instance.data["last_version_published_files"]. All these but frames
    mentioned in text field will be reused for new version.
    """
    order = pyblish.api.CollectorOrder + 0.495
    label = "Collect Frames to Fix"
    targets = ["local"]
    families = ["*"]

    rewrite_version_enable = False

    def process(self, instance):
        # Skip instances that are set to not be integrated so we ignore
        # the original `render` instance from which local AOV instances are
        # spawned off.
        if not instance.data.get("integrate", True):
            return

        attribute_values = self.get_attr_values_from_data(instance.data)
        frames_to_fix: str = attribute_values.get("frames_to_fix", "")
        rewrite_version: bool = attribute_values.get("rewrite_version", False)
        if not frames_to_fix:
            return

        instance.data["frames_to_fix"] = frames_to_fix

        product_name: str = instance.data["productName"]
        folder_entity: dict = instance.data["folderEntity"]
        project_entity: dict = instance.data["projectEntity"]
        project_name: str = project_entity["name"]

        version_entity = ayon_api.get_last_version_by_product_name(
            project_name,
            product_name,
            folder_entity["id"]
        )
        if not version_entity:
            self.log.warning(
                "No last version found, re-render not possible"
            )
            return

        representations = ayon_api.get_representations(
            project_name, version_ids={version_entity["id"]}
        )
        published_files: "list[str]" = []
        for repre in representations:
            # TODO get product type from product entity instead of
            #   representation 'context' data.
            repre_context = repre["context"]
            product_type = repre_context.get("product", {}).get("type")
            if not product_type:
                product_type = repre_context.get("family")
            if "*" not in self.families and product_type not in self.families:
                continue

            for file_info in repre.get("files"):
                published_files.append(file_info["path"])

        instance.data["last_version_published_files"] = published_files
        self.log.debug(f"last_version_published_files: {published_files}")

        if self.rewrite_version_enable and rewrite_version:
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
                        "frame range."
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
