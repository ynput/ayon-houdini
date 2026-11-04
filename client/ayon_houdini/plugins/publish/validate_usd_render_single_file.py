# -*- coding: utf-8 -*-
import inspect
import hou
import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError, RepairAction

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateUSDRenderSingleFile(plugin.HoudiniInstancePlugin):
    """Validate the writing of a single USD Render Output file.

    When writing to single file with USD Render ROP make sure to write the
    output USD file from a single process to avoid overwriting it with
    different processes.

    Exporting the file in a single farm task is handled by the farm
    submitter, see `splitRenderFrameDependent` in `CollectUsdRender`.
    """

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render ROP Settings"
    actions = [SelectROPAction, RepairAction]

    def process(self, instance):

        if instance.data.get("creator_attributes",
                             {}).get("render_target") != "farm_split":
            # Validation is only relevant when submitting a farm job where the
            # export and render are separate jobs.
            return

        if "$F" in instance.data["ifdFile"]:
            # A USD file per frame can be written by any process.
            return

        # Whether ROP node is set to render all Frames within a single process
        # When this is disabled then Husk will restart completely per frame
        # and each frame overwrites the single USD file.
        rop_node = hou.node(instance.data["instance_node"])
        if not rop_node.evalParm("allframesatonce"):
            self.log.error(
                "Please enable 'Render All Frames With A Single Process' "
                "on the USD Render ROP node or add $F to the USD filename",
            )
            raise PublishValidationError(
                "Render USD file being overwritten during export.",
                title="Render USD file overwritten",
                description=self.get_description())

    @classmethod
    def repair(cls, instance):
        rop_node = hou.node(instance.data["instance_node"])
        rop_node.parm("allframesatonce").set(True)

    def get_description(self):
        return inspect.cleandoc(
            """### Render USD file configured incorrectly

            The USD render ROP is currently configured to write a single
            USD file to render instead of a file per frame.

            When that is the case, a single process must produce that file
            to avoid the file being overwritten by the other processes.

            We resolve that by enabling _Render All Frames With A Single
            Process_ on the ROP node.

            Run **Repair** to resolve this for you.

            If instead you want to write separate render USD files, please
            include $F in the USD output filename on the `ROP node > Output >
            USD Export > Output File`
            """
        )
