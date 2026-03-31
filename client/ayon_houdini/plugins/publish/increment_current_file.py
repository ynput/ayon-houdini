import os

import pyblish.api

from ayon_core.lib import version_up
from ayon_core.pipeline import (
    registered_host,
    KnownPublishError
)
from ayon_core.host import IWorkfileHost
from ayon_core.pipeline.publish import get_errored_plugins_from_context

from ayon_houdini.api import plugin


class IncrementCurrentFile(plugin.HoudiniContextPlugin):
    """Increment the current file.

    Saves the current scene with an increased version number.

    """

    label = "Increment current file"
    order = pyblish.api.IntegratorOrder + 9.0
    families = ["workfile",
                "usdrender",
                "mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "render.local.hou",
                "publish.hou"]
    optional = True

    def process(self, context):

        errored_plugins = get_errored_plugins_from_context(context)
        if any(
            plugin.__name__ == "HoudiniSubmitPublishDeadline"
            for plugin in errored_plugins
        ):
            raise KnownPublishError(
                "Skipping incrementing current file because "
                "submission to deadline failed."
            )

        # Filename must not have changed since collecting.
        host = registered_host()
        current_filepath: str = host.get_current_workfile()
        if context.data["currentFile"] != current_filepath:
            raise KnownPublishError(
                f"Collected filename '{context.data['currentFile']}' differs"
                f" from current scene name '{current_filepath}'."
            )

        try:
            from ayon_core.pipeline.workfile import save_next_version
            from ayon_core.host.interfaces import SaveWorkfileOptionalData

            current_filename = os.path.basename(current_filepath)
            save_next_version(
                description=(
                    f"Incremented by publishing from {current_filename}"
                ),
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        except ImportError:
            # Backwards compatibility before ayon-core 1.5.0
            self.log.debug(
                "Using legacy `version_up`. Update AYON core addon to "
                "use newer `save_next_version` function."
            )
            new_filepath = version_up(current_filepath)
            host: IWorkfileHost = registered_host()
            host.save_workfile(new_filepath)
