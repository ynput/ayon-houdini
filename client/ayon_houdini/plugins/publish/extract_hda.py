# -*- coding: utf-8 -*-
import contextlib
import os
import tempfile

import hou
import pyblish.api

from ayon_core.pipeline import PublishError
from ayon_houdini.api import plugin


@contextlib.contextmanager
def revert_original_parm_template_group(node: "hou.OpNode"):
    """Restore parm template group after the context"""
    parm_group = node.parmTemplateGroup()
    try:
        yield
    finally:
        # Set the original
        node.setParmTemplateGroup(parm_group)


class ExtractHDA(plugin.HoudiniExtractorPlugin):

    order = pyblish.api.ExtractorOrder
    label = "Extract HDA"
    families = ["hda"]

    def process(self, instance):

        hda_node = hou.node(instance.data.get("instance_node"))
        hda_def = hda_node.type().definition()
        hda_options = hda_def.options()
        hda_options.setSaveInitialParmsAndContents(True)

        next_version = instance.data["anatomyData"]["version"]
        self.log.info("setting version: {}".format(next_version))
        hda_def.setVersion(str(next_version))
        hda_def.setOptions(hda_options)

        hda_file_path = hda_def.libraryFilePath()

        # if the HDA is embedded, we need to save it so that it can be copied
        # to the staging and publish directories
        if hda_file_path == "Embedded":
            _, hda_file_path = tempfile.mkstemp(suffix=".hda")

            instance.context.data["cleanupFullPaths"].append(hda_file_path)

        with revert_original_parm_template_group(hda_node):
            # Remove our own custom parameters so that if the HDA definition
            # has "Save Spare Parameters" enabled, we don't save our custom
            # attributes
            # Get our custom `Extra` AYON parameters
            parm_group = hda_node.parmTemplateGroup()
            # The name 'Extra' is a hard coded name in AYON.
            parm_folder = parm_group.findFolder("Extra")
            if not parm_folder:
                raise PublishError(
                    "Extra AYON parm folder does not exist"
                    f" on {hda_node.path()}"
                    "\n\nPlease select the node and create an"
                    " HDA product from the publisher UI."
                )

            # Remove `Extra` AYON parameters
            parm_group.remove(parm_folder.name())
            hda_node.setParmTemplateGroup(parm_group)

            # Save the HDA file
            hda_def.save(hda_file_path, hda_node, hda_options)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        file = os.path.basename(hda_file_path)
        staging_dir = os.path.dirname(hda_file_path)
        self.log.debug(f"Using HDA from {hda_file_path}")

        representation = {
            'name': 'hda',
            'ext': 'hda',
            'files': file,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
