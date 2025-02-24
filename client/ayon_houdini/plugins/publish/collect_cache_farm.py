import os
import hou
import pyblish.api
from ayon_houdini.api import (
    lib,
    plugin
)


class CollectFarmCacheFamily(plugin.HoudiniInstancePlugin):
    """Collect publish.hou family for caching on farm as early as possible."""
    order = pyblish.api.CollectorOrder - 0.45
    families = ["ass", "pointcache", "redshiftproxy",
                "vdbcache", "model", "staticMesh",
                 "rop.opengl", "usdrop", "camera"]
    targets = ["local", "remote"]
    label = "Collect Data for Cache"

    def process(self, instance):

        if not instance.data["farm"]:
            self.log.debug("Caching on farm is disabled. "
                           "Skipping farm collecting.")
            return
        instance.data["families"].append("publish.hou")


class CollectDataforCache(plugin.HoudiniInstancePlugin):
    """Collect data for caching to Deadline."""

    # Run after Collect Frames
    order = pyblish.api.CollectorOrder + 0.11
    families = ["publish.hou"]
    targets = ["local", "remote"]
    label = "Collect Data for Cache"

    def process(self, instance):
        # Why do we need this particular collector to collect the expected
        # output files from a ROP node. Don't we have a dedicated collector
        # for that yet?
        # Answer: No, we don't have a generic expected file collector.
        #         Because different product types needs different logic.
        #         e.g. check CollectMantraROPRenderProducts
        #               and CollectKarmaROPRenderProducts
        # Collect expected files
        ropnode = hou.node(instance.data["instance_node"])
        output_parm = lib.get_output_parameter(ropnode)
        expected_filepath = output_parm.eval()

        files = instance.data.setdefault("files", list())
        frames = instance.data.get("frames", "")
        if isinstance(frames, str):
            # single file
            files.append(expected_filepath)
        else:
            # list of files
            staging_dir, _ = os.path.split(expected_filepath)
            files.extend("{}/{}".format(staging_dir, f) for f in frames)

        expected_files = instance.data.setdefault("expectedFiles", list())
        expected_files.append({"cache": files})
        self.log.debug(f"Caching on farm expected files: {expected_files}")

        instance.data.update({
             # used in HoudiniCacheSubmitDeadline in ayon-deadline
            "plugin": "Houdini",
            "publish": True
        })
