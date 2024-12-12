import inspect
import pyblish.api

from ayon_core.lib import version_up
from ayon_core.pipeline import (
    registered_host,
    KnownPublishError,
    PublishError
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

        # Filename must not have changed since collecting
        host = registered_host()
        current_file = host.current_file()
        if context.data["currentFile"] != current_file:
            raise PublishError(
                f"Collected filename '{context.data['currentFile']}' differs"
                f" from current scene name '{current_file}'.",
                description=self.get_error_description()
            )

        new_filepath = version_up(current_file)
        host.save_workfile(new_filepath)

    def get_error_description(self):
        return inspect.cleandoc(
            """### Scene File Name Change During Publishing
            This error occurs when you validate the scene and then save it as a new file manually, or if you open a new file and continue publishing.
            Please reset the publisher and publish without changing the scene file midway.
            """
        )