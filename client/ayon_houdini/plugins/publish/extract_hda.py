# -*- coding: utf-8 -*-
import os
import contextlib

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
                    f"Extra parm folder does not exist: {hda_node.path()}"
                )

            # Remove `Extra` AYON parameters
            parm_group.remove(parm_folder.name())
            hda_node.setParmTemplateGroup(parm_group)

            # Save the HDA file
            hda_def.save(hda_def.libraryFilePath(), hda_node, hda_options)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        file = os.path.basename(hda_def.libraryFilePath())
        staging_dir = os.path.dirname(hda_def.libraryFilePath())
        self.log.info("Using HDA from {}".format(hda_def.libraryFilePath()))

        representation = {
            'name': 'hda',
            'ext': 'hda',
            'files': file,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
