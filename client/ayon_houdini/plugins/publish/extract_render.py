import os
import hou

import pyblish.api

from ayon_core.pipeline import PublishError
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import format_as_collections


class ExtractRender(plugin.HoudiniExtractorPlugin):

    order = pyblish.api.ExtractorOrder
    label = "Extract Render"
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender"]

    def process(self, instance):
        creator_attribute = instance.data["creator_attributes"]
        rop_node = hou.node(instance.data.get("instance_node"))
        node_type = rop_node.type().name()

        # TODO: This section goes against pyblish concepts where
        # pyblish plugins should change the state of the scene.
        # However, in ayon publisher tool users can have options and
        # these options should some how synced with the houdini nodes.
        # More info: https://github.com/ynput/ayon-core/issues/417

        # Align split parameter value on rop node to the render target.
        if instance.data["splitRender"]:
            if node_type == "arnold":
                rop_node.setParms({"ar_ass_export_enable": 1})
            elif node_type == "ifd":
                rop_node.setParms({"soho_outputmode": 1})
            elif node_type == "Redshift_ROP":
                rop_node.setParms({"RS_archive_enable": 1})
            elif node_type == "vray_renderer":
                rop_node.setParms({"render_export_mode": "2"})
            elif node_type == "usdrender":
                rop_node.setParms({"runcommand": 0})
        else:
            if node_type == "arnold":
                rop_node.setParms({"ar_ass_export_enable": 0})
            elif node_type == "ifd":
                rop_node.setParms({"soho_outputmode": 0})
            elif node_type == "Redshift_ROP":
                rop_node.setParms({"RS_archive_enable": 0})
            elif node_type == "vray_renderer":
                rop_node.setParms({"render_export_mode": "1"})
            elif node_type == "usdrender":
                rop_node.setParms({"runcommand": 1})

        if instance.data.get("farm"):
            self.log.debug("Render should be processed on farm, skipping local render.")
            return

        if creator_attribute.get("render_target") == "local":
            # FIXME Render the entire frame range if any of the AOVs does not have a
            # previously rendered version. This situation breaks the publishing.
            # because There will be missing frames as ROP nodes typically cannot render different
            #  frame ranges for each AOV; they always use the same frame range for all AOVs.
            self.render_rop(instance)

        # `ExpectedFiles` is a list that includes one dict.
        expected_files = instance.data["expectedFiles"][0]
        # Each key in that dict is a list of files.
        # Combine lists of files into one big list.
        all_frames = []
        for value in  expected_files.values():
            if isinstance(value, str):
                all_frames.append(value)
            elif isinstance(value, list):
                all_frames.extend(value)
        # Check missing frames.
        # Frames won't exist if user cancels the render.
        missing_frames = [
            frame
            for frame in all_frames
            if not os.path.exists(frame)
        ]

        if missing_frames:
            # Combine collections for simpler logs of missing files
            missing_frames  = format_as_collections(missing_frames)
            missing_frames = "\n ".join(f"- {sequence}" for sequence in missing_frames)
            raise PublishError(
                "Failed to complete render extraction.\n"
                "Please render any missing output files.",
                detail=f"Missing output files: \n {missing_frames}"
            )
