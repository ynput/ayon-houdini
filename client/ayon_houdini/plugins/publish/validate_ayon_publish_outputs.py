"""Validator for the representations collected from the AYON Publish ROP."""
import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_houdini.api import plugin


class ValidateAYONPublishOutputs(plugin.HoudiniInstancePlugin):
    """Validate the representations of an AYON Publish ROP instance.

    Every input ROP must provide a usable output file and each input must
    result in a unique representation (name/extension). Two inputs with the
    same extension would collide during integration, and an input without an
    output file (e.g. an OpenGL ROP without an output image) would create an
    unusable representation.
    """

    order = pyblish.api.ValidatorOrder
    families = ["rop_publish"]
    label = "Validate AYON Publish Outputs"

    def process(self, instance):
        representations = instance.data.get("representations") or []
        if not representations:
            raise PublishValidationError(
                "No output representations were collected for the AYON "
                "Publish ROP. Connect at least one input ROP with a valid "
                "output file.",
                title=self.label,
            )

        invalid = [
            representation for representation in representations
            if not representation.get("ext")
            or not representation.get("files")
        ]
        if invalid:
            raise PublishValidationError(
                "Some input ROPs do not have a usable output file. Give each "
                "input ROP an output path (for OpenGL ROPs set an output "
                "image; 'ip'/'md' do not write files to disk).",
                detail="Invalid representations:\n{}".format(invalid),
                title=self.label,
            )

        extensions = {}
        for representation in representations:
            ext = str(representation.get("ext", "")).lower()
            extensions.setdefault(ext, 0)
            extensions[ext] += 1

        duplicates = sorted(
            ext for ext, count in extensions.items() if count > 1
        )
        if duplicates:
            raise PublishValidationError(
                "Multiple input ROPs export the same file extension. Each "
                "input ROP must use a unique extension or representation "
                "name, otherwise their representations would overwrite each "
                "other during publishing.",
                detail=(
                    "Duplicate extensions: {}\n"
                    "Collected representations:\n{}".format(
                        ", ".join(duplicates),
                        [
                            representation.get("name")
                            for representation in representations
                        ],
                    )
                ),
                title=self.label,
            )
