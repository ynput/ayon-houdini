import os
import hou

import pyblish.api
from ayon_houdini.api import plugin


class CollectHoudiniCurrentFile(plugin.HoudiniContextPlugin):
    """Inject the current working file into context"""

    order = pyblish.api.CollectorOrder - 0.1
    label = "Houdini Current File"

    def process(self, context):
        """Inject the current working file"""

        current_file = hou.hipFile.path()
        if (
                hou.hipFile.isNewFile()
                or not os.path.exists(current_file)
        ):
            # By default, Houdini will even point a new scene to a path.
            # However if the file is not saved at all and does not exist,
            # we assume the user never set it.
            self.log.warning("Houdini workfile is unsaved.")
            current_file = ""

        context.data["currentFile"] = current_file
        self.log.info('Current workfile path: {}'.format(current_file))
