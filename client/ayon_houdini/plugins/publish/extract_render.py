import os
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

        do_local_render = (
            creator_attribute.get("render_target")
            in {"local", "local_export_farm_render"}
        )

        if instance.data.get("farm") and not do_local_render:
            self.log.debug(
                "Render should be processed on farm, skipping local render."
            )
            return

        if do_local_render:
            # FIXME Render the entire frame range if any of the AOVs does
            #   not have a previously rendered version. This situation breaks
            #   the publishing.
            # because There will be missing frames as ROP nodes typically
            #   cannot render different frame ranges for each AOV; they always
            #   use the same frame range for all AOVs.
            self.render_rop(instance)

        if (
            creator_attribute.get("render_target")
            == "local_export_farm_render"
        ):
            return

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
            missing_frames = "\n ".join(
                f"- {sequence}" for sequence in missing_frames
            )
            raise PublishError(
                "Failed to complete render extraction.\n"
                "Please render any missing output files.",
                detail=f"Missing output files: \n {missing_frames}"
            )
