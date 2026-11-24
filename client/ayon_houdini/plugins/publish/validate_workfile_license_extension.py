import inspect
import os

import pyblish.api

from ayon_core.pipeline import registered_host, PublishValidationError
from ayon_core.pipeline.workfile import save_next_version
from ayon_core.tools.utils.host_tools import show_workfiles

from ayon_houdini.api import plugin


class SaveByVersionUpAction(pyblish.api.Action):
    """Save Workfile."""
    label = "Save Workfile"
    on = "failed"
    icon = "save"

    def process(self, context, plugin):
        save_next_version()


class ShowWorkfilesAction(pyblish.api.Action):
    """Save Workfile."""
    label = "Show Workfiles Tool..."
    on = "failed"
    icon = "files-o"

    def process(self, context, plugin):
        show_workfiles()


class ValidateWorkfileLicenseExtension(plugin.HoudiniContextPlugin):
    """Validate the workfile extension matches the Houdini license.

    Houdini saves the scene in its license's format, e.g. a commercial
    '.hip' opened with an Apprentice license saves as non-commercial. The
    workfile extension must match that format.

    """

    label = "Workfile Extension Matches License"
    order = pyblish.api.ValidatorOrder - 0.1
    actions = [SaveByVersionUpAction, ShowWorkfilesAction]

    def process(self, context):
        current_file = context.data["currentFile"]
        if not current_file:
            # 'ValidateCurrentSaveFile' reports unsaved scenes
            return

        extension = os.path.splitext(current_file)[1]
        save_extensions = registered_host().get_workfile_save_extensions()
        if extension not in save_extensions:
            raise PublishValidationError(
                f"Workfile '{os.path.basename(current_file)}' doesn't match"
                f" this Houdini license, which saves '{save_extensions[0]}'"
                " files.",
                title="Workfile extension doesn't match license",
                description=self.get_description(
                    extension, save_extensions[0]
                ),
            )

    @staticmethod
    def get_description(extension, save_extension):
        return inspect.cleandoc(f"""
            ### Workfile extension doesn't match license

            The current workfile is a `{extension}` file, but this Houdini
            license saves `{save_extension}` files.

            The **Save Workfile** action saves it as the next workfile
            version with the `{save_extension}` extension. Reset the
            publisher afterwards to continue publishing.
        """)
