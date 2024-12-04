import pyblish.api

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.publish import PublishError

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
                message="Collected filename from current scene name."
            )

        if host.workfile_has_unsaved_changes():
            self.log.info("Saving current file: {}".format(current_file))
            host.save_workfile(current_file)
        else:
            self.log.debug("No unsaved changes, skipping file save..")
