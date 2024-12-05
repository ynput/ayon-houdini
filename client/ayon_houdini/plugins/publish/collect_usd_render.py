import os
import re

import hou
import pyblish.api

from ayon_core.pipeline import PublishError
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import evalParmNoFrame


class CollectUsdRender(plugin.HoudiniInstancePlugin):
    """Collect publishing data for USD Render ROP.

    If `rendercommand` parm is disabled (and thus no rendering triggers by the
    usd render rop) it is assumed to be a "Split Render" job where the farm
    will get an additional render job after the USD file is extracted.

    Provides:
        instance    -> ifdFile

    """

    label = "Collect USD Render Rop"
    order = pyblish.api.CollectorOrder
    hosts = ["houdini"]
    families = ["usdrender"]

    def process(self, instance):

        rop = hou.node(instance.data.get("instance_node"))

        if instance.data["splitRender"]:
            # USD file output
            lop_output = self.evalParmNoFrame(
                rop, "lopoutput", pad_character="#"
            )

            # The file is usually relative to the Output Processor's 'Save to
            # Directory' which forces all USD files to end up in that directory
            # TODO: It is possible for a user to disable this
            # TODO: When enabled I think only the basename of the `lopoutput`
            #  parm is preserved, any parent folders defined are likely ignored
            folder = self.evalParmNoFrame(
                rop, "savetodirectory_directory", pad_character="#"
            )

            export_file = os.path.join(folder, lop_output)

            # Substitute any # characters in the name back to their $F4
            # equivalent
            def replace_to_f(match):
                number = len(match.group(0))
                if number <= 1:
                    number = ""  # make it just $F not $F1 or $F0
                return "$F{}".format(number)

            export_file = re.sub("#+", replace_to_f, export_file)
            self.log.debug(
                "Found export file: {}".format(export_file)
            )
            instance.data["ifdFile"] = export_file

            # The render job is not frame dependent but fully dependent on
            # the job having been completed, since the extracted file is a
            # single file.
            if "$F" not in export_file:
                instance.data["splitRenderFrameDependent"] = False

        # stub required data for Submit Publish Job publish plug-in
        instance.data["attachTo"] = []

    def evalParmNoFrame(self, rop, parm, **kwargs):
        try:
            return evalParmNoFrame(rop, parm, **kwargs)
        except Exception as exc:
            raise PublishError(
                f"Failed evaluating parameter '{parm}' on Rop node: {rop.path()}",
                detail=f"{exc}"
            )