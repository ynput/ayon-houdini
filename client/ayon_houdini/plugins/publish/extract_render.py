import os
import hou
import clique 

import pyblish.api

from ayon_houdini.api import plugin
from ayon_houdini.api.lib import render_rop


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
        product_type = instance.data["productType"]
        rop_node = hou.node(instance.data.get("instance_node"))

        # TODO: This section goes against pyblish concepts where
        # pyblish plugins should change the state of the scene.
        # However, in ayon publisher tool users can have options and
        # these options should some how synced with the houdini nodes.
        # More info: https://github.com/ynput/ayon-core/issues/417

        # Align split parameter value on rop node to the render target.
        if instance.data["splitRender"]:
            if product_type == "arnold_rop":
                rop_node.setParms({"ar_ass_export_enable": 1})
            elif product_type == "mantra_rop":
                rop_node.setParms({"soho_outputmode": 1})
            elif product_type == "redshift_rop":
                rop_node.setParms({"RS_archive_enable": 1})
            elif product_type == "vray_rop":
                rop_node.setParms({"render_export_mode": "2"})
            elif product_type == "usdrender":
                rop_node.setParms({"runcommand": 0})
        else:
            if product_type == "arnold_rop":
                rop_node.setParms({"ar_ass_export_enable": 0})
            elif product_type == "mantra_rop":
                rop_node.setParms({"soho_outputmode": 0})
            elif product_type == "redshift_rop":
                rop_node.setParms({"RS_archive_enable": 0})
            elif product_type == "vray_rop":
                rop_node.setParms({"render_export_mode": "1"})
            elif product_type == "usdrender":
                rop_node.setParms({"runcommand": 1})

        if instance.data.get("farm"):
            self.log.debug("Render should be processed on farm, skipping local render.")
            return

        if creator_attribute.get("render_target") == "local":
            # FIXME Render the entire frame range if any of the AOVs does not have a
            # previously rendered version. This situation breaks the publishing.
            # because There will be missing frames as ROP nodes typically cannot render different
            #  frame ranges for each AOV; they always use the same frame range for all AOVs.
            rop_node = hou.node(instance.data.get("instance_node"))
            frames_to_fix = clique.parse(instance.data.get("frames_to_fix", ""), "{ranges}")

            if len(set(frames_to_fix)) > 1:
                # Render only frames to fix
                for frame_range in frames_to_fix.separate():
                    frame_range = list(frame_range)
                    self.log.debug(
                        "Rendering frames to fix [{f1}, {f2}]".format(
                            f1=frame_range[0],
                            f2=frame_range[-1]
                        )
                    )
                    # for step to be 1 since clique doesn't support steps.
                    frame_range = (
                        int(frame_range[0]), int(frame_range[-1]), 1
                    )
                    render_rop(rop_node, frame_range=frame_range)
            else:
                render_rop(rop_node)

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
            # TODO: Use user friendly error reporting.
            raise RuntimeError("Failed to complete render extraction. "
                               "Missing output files: {}".format(
                                   missing_frames))
