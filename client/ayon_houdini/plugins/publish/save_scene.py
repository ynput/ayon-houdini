import inspect
import os

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
            # Houdini saves with its license's extension, so saving a '.hip'
            # with an Indie license writes a '.hiplc' and the scene path
            # changes.
            saved_file = host.get_current_workfile()
            if saved_file != current_file:
                self.log.info(
                    f"Houdini saved the file as '{saved_file}' to match its"
                    " license. Publishing continues with that file."
                )
                self.update_current_file(context, current_file, saved_file)
        else:
            self.log.debug("No unsaved changes, skipping file save..")

    def update_current_file(self, context, old_file, new_file):
        """Update the workfile path in the context and instance data.

        The path appears in 'context.data["currentFile"]' and in the
        workfile instance's 'setMembers' and representation, which
        'CollectWorkfile' copied from the collected path before this plugin.

        This is only needed when the file was opened with a different
        license, so Houdini saved it with a different extension,
        e.g. '.hiplc' instead of '.hip'.

        Args:
            context (pyblish.api.Context): Publish context.
            old_file (str): Collected path of the current file.
            new_file (str): Path Houdini actually saved the file to.

        """
        context.data["currentFile"] = new_file

        old_name = os.path.basename(old_file)
        staging_dir, new_name = os.path.split(new_file)
        ext = os.path.splitext(new_name)[1].lstrip(".")
        for instance in context:
            families = {instance.data.get("family")}
            families.update(instance.data.get("families", []))
            if "workfile" not in families:
                continue

            set_members = instance.data.get("setMembers")
            if set_members == [old_file]:
                instance.data["setMembers"] = [new_file]

            for repre in instance.data.get("representations", []):
                if repre.get("files") != old_name:
                    continue
                repre.update({
                    "name": ext,
                    "ext": ext,
                    "files": new_name,
                    "stagingDir": staging_dir,
                })

    def get_error_description(self):
        return inspect.cleandoc(
            """### Scene File Name Changed During Publishing
            This error occurs when you validate the scene and then save it as
            a new file manually, or if you open a new file and continue
            publishing.

            Please reset the publisher and publish without changing
            the scene file midway.
            """
        )
