import os
import shutil

import clique
import pyblish.api

from ayon_core.lib import collect_frames
from ayon_houdini.api import plugin


class ExtractLastPublished(plugin.HoudiniExtractorPlugin):
    """Extractor copying files from last published to staging directory.

    It works only if instance data includes "last_version_published_files"
    and there are frames to fix.

    The files from last published are based on files which will be
    extended/fixed for specific frames.

    NOTE: 
        This plugin is closely taken from ayon-nuke.
        It contains some Houdini addon specific logic as various addons may
          have unique methods for managing `staging_dir`, `expectedFiles`
          and `frames`.
    TODO:
        It's preferable to to generalize this plugin for broader use and
          integrate it into ayon-core.
    """

    order = pyblish.api.ExtractorOrder - 0.1
    label = "Extract Last Published"
    targets = ["local"]  # Same target as `CollectFramesFixDef`
    families = ["*"]

    def process(self, instance):
        frames_to_fix = instance.data.get("frames_to_fix")
        if not frames_to_fix:
            self.log.debug("Skipping, No frames to fix.")
            return
        
        if not instance.data.get("integrate", True):
            self.log.debug("Skipping collecting frames to fix data for "
                           "instance because instance is set to not integrate")
            return

        last_published = instance.data.get("last_version_published_files")
        if not last_published:
            self.log.debug("Skipping, No last publish found.")
            return

        last_published_and_frames = collect_frames(last_published)
        if not all(last_published_and_frames.values()):
            self.log.debug("Skipping, No file sequence found in the "
                           "last version published files.")
            return

        staging_dir, expected_filenames = self.get_expected_files_and_staging_dir(instance)

        os.makedirs(staging_dir, exist_ok=True)

        expected_and_frames = collect_frames(expected_filenames)
        frames_and_expected = {v: k for k, v in expected_and_frames.items()}
        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")
        
        anatomy = instance.context.data["anatomy"]

        # TODO: This currently copies ALL frames from the last version instead
        #  of only those within the frame range we're currently looking to
        #  publish. It should instead, iterate over all expected frames for
        #  current instance, exclude all "to fix" frames and copy the
        #  other existing ones.
        for file_path, frame in last_published_and_frames.items():
            if frame is None:
                continue
            file_path = anatomy.fill_root(file_path)
            if not os.path.exists(file_path):
                continue
            target_file_name = frames_and_expected.get(frame)
            if not target_file_name:
                continue
            
            out_path = os.path.join(staging_dir, target_file_name)

            # Copy only the frames that we won't render.
            if frame and frame not in frames_to_fix:
                self.log.debug(f"Copying '{file_path}' -> '{out_path}'")
                shutil.copy(file_path, out_path)

    def get_expected_files_and_staging_dir(self, instance):
        """Get expected file names or frames.

        This method includes Houdini specific code.

        Args:
            instance (pyblish.api.Instance): The instance to publish.

        Returns:
            tuple[str, list[str]]: A 2-tuple of staging dir and the list of
                expected frames for the current publish instance.
        """
        expected_filenames = []
        staging_dir = instance.data.get("stagingDir")
        expected_files = instance.data.get("expectedFiles", [])

        # 'expectedFiles' are preferred over 'frames'
        if expected_files:
            # Products with expected files
            # This can be Render products or submitted cache to farm.
            for expected in expected_files:
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

        return staging_dir, expected_filenames
