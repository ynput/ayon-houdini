import inspect
import pyblish.api

from ayon_core.pipeline import registered_host, PublishError

from ayon_houdini.api import plugin


class SaveCurrentScene(plugin.HoudiniContextPlugin):
    """Save current scene"""

    label = "Save current file"
    order = pyblish.api.ExtractorOrder - 0.49

    def process(self, context):

        # Filename must not have changed since collecting
        host = registered_host()
        current_file = host.get_current_workfile()
        if context.data['currentFile'] != current_file:
            raise PublishError(
                f"Collected filename '{context.data['currentFile']}' differs"
                f" from current scene name '{current_file}'.",
                description=self.get_error_description()
            )
        if host.workfile_has_unsaved_changes():
            self.log.info("Saving current file: {}".format(current_file))
            host.save_workfile(current_file)
        else:
            self.log.debug("No unsaved changes, skipping file save..")


    def get_error_description(self):
        return inspect.cleandoc(
            """### Scene File Name Changed During Publishing
            This error occurs when you validate the scene and then save it as a new file manually, or if you open a new file and continue publishing.
            Please reset the publisher and publish without changing the scene file midway.
            """
        )