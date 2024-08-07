import os
import shutil

import clique
import pyblish.api

from ayon_core.lib import collect_frames
from ayon_houdini.api import plugin


class ExtractLastPublished(plugin.HoudiniExtractorPlugin):
    """
    Generic Extractor that copies files from last published
    to staging directory.
    It works only if instance data includes "last_version_published_files"
    and there are frames to fix.

    The files from last published are base of files which will be extended/fixed for specific
    frames.
    """

    order = pyblish.api.ExtractorOrder - 0.1
    label = "Extract Last Published"
    targets = ["local"]  # Same target as `CollectFramesFixDef`
    families = ["*"]

    def process(self, instance):
        frames_to_fix = instance.data.get("frames_to_fix")
        last_published = instance.data.get("last_version_published_files")
        if not last_published:
            self.log.debug("Skipping, No last publish found.")
            return 
        if not frames_to_fix :
            self.log.debug("Skipping, No frames to fix.")
            return
        last_published_and_frames = collect_frames(last_published)
        
        if not all(last_published_and_frames.values()):
            # Reset last_version_published_files.
            # This is needed for later extractors.
            instance.data["last_version_published_files"] = None
            self.log.debug("Skipping, No file sequence found in the "
                           "last version published files.")

        expected_filenames = []
        staging_dir = instance.data.get("stagingDir")
        expectedFiles = instance.data.get("expectedFiles", [])

        # 'expectedFiles' are preferred over 'frames'
        if expectedFiles:
            # Products with expected files
            # This can be Render products or submitted cache to farm.
            for expected in expectedFiles:
                # expected.values() is a list of lists
                expected_filenames.extend(sum(expected.values(), []))
        else:
            # Products with frames or single file.
            frames = instance.data.get("frames", "")
            if isinstance(frames, str):
                # single file.
                expected_filenames.append("{}/{}".format(staging_dir, frames))
            else:
                # list of frame.
                expected_filenames.extend(
                    ["{}/{}".format(staging_dir, f) for f in frames]
                )

        os.makedirs(staging_dir, exist_ok=True)

        expected_and_frames = collect_frames(expected_filenames)
        frames_and_expected = {v: k for k, v in expected_and_frames.items()}
        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")
        
        anatomy = instance.context.data["anatomy"]

        for file_path, frame in last_published_and_frames.items():
            if frame is None:
                continue
            file_path = anatomy.fill_root(file_path)
            if not os.path.exists(file_path):
                continue
            target_file_name = frames_and_expected.get(frame)
            if not target_file_name:
                continue
            
            # FIXME This won't work with render products.
            out_path = os.path.join(staging_dir, target_file_name)

            # Copy only the frames that we won't render.
            if frame and frame not in frames_to_fix:
                self.log.debug("Copying '{}' -> '{}'".format(file_path, out_path))
                shutil.copy(file_path, out_path)
