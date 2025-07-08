import pyblish.api

from ayon_core.lib import version_up
from ayon_core.pipeline import (
    registered_host,
    KnownPublishError
)
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
        current_file = host.get_current_workfile()
        if context.data["currentFile"] != current_file:
            raise KnownPublishError(
                f"Collected filename '{context.data['currentFile']}' differs"
                f" from current scene name '{current_file}'."
            )

        new_filepath = version_up(current_file)

        if hasattr(host, "save_workfile_with_context"):
            from ayon_core.host.interfaces import SaveWorkfileOptionalData
            host.save_workfile_with_context(
                filepath=new_filepath,
                folder_entity=context.data["folderEntity"],
                task_entity=context.data["taskEntity"],
                description="Incremented by publishing.",
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        else:
            # Backwards compatibility
            host.save_workfile(new_filepath)
