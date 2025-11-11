import os
import hou
import clique
from typing import Optional

import pyblish.api

from ayon_houdini.api import plugin


def get_clip_frames_in_frame_range(
        clip_start: int, 
        clip_end: int,
        has_end_set: bool,
        loop: bool, 
        range_start: int, 
        range_end: int):
    """Calculate which clip frames are visible in the given frame range.

    Args:
        clip_start: Start frame of sequence (X)
        clip_end: End frame of sequence (Y)
        has_end_set: Whether clip end applies or it's infinite.
        loop: Whether sequence loops after end
        range_start: Start of query range (e.g., 1001)
        range_end: End of query range (e.g., 1100)

    Returns:
        set[int]: Set of sequence frames visible in the range
    """
    visible_frames = set()

    # Case 1: No end frame - sequence runs infinitely from start
    if not has_end_set:
        if clip_start <= range_end:
            # All frames from max(seq_start, range_start) to range_end are
            # included
            start = max(clip_start, range_start)
            visible_frames = set(range(start, range_end + 1))
        return visible_frames

    # Case 2: Has end frame, no loop - sequence plays once
    if not loop:
        clip_end += 1  # Houdini exports an additional frame when not looping
        # Intersection of [clip_start, clip_end] and [range_start, range_end]
        intersection_start = max(clip_start, range_start)
        intersection_end = min(clip_end, range_end)
        if intersection_start <= intersection_end:
            visible_frames = set(
                range(intersection_start, intersection_end + 1))
        return visible_frames

    # Case 3: Has end frame and loops
    loop_duration = clip_end - clip_start + 1

    for frame in range(range_start, range_end + 1):
        if frame < clip_start:
            # Before sequence starts - not visible
            continue
        elif frame <= clip_end:
            # Within first play of sequence
            visible_frames.add(frame)
        else:
            # After first play - map to looped frame
            offset = (frame - clip_start) % loop_duration
            looped_frame = clip_start + offset
            visible_frames.add(looped_frame)

    return visible_frames


class CollectUSDValueClips(plugin.HoudiniInstancePlugin):
    """Collect USD value clips that are to be written out for a USD publish.

    It detects sequence clips inside the current stage
    to be written on executing a USD ROP.

    """
    label = "Collect USD Value Clips"
    # Run after core plugin `CollectResourcesPath`
    order = pyblish.api.CollectorOrder + 0.496
    families = ["usd"]

    def process(self, instance):
        # For each layer in the output layer stack process any USD Value Clip
        # nodes that are listed as 'editor nodes' in that graph.
        for layer in instance.data.get("layers", []):
            self._get_layer_value_clips(layer, instance)

    def _get_layer_value_clips(self, layer, instance):
        info_prim = layer.GetPrimAtPath("/HoudiniLayerInfo")
        if not info_prim:
            return

        editor_nodes = info_prim.customData.get("HoudiniEditorNodes")
        if not editor_nodes:
            return

        # Get frame range of the ROP node
        start: int = int(instance.data["frameStartHandle"])
        end: int = int(instance.data["frameEndHandle"])

        asset_remap = instance.data.setdefault("assetRemap", {})
        for node_id in editor_nodes:
            # Consider only geoclipsequence nodes
            node = hou.nodeBySessionId(node_id)
            if node.type().name() != "geoclipsequence":
                continue

            self.log.debug(
                f"Collecting outputs for Geometry Clip Sequence: {node.path()}"
            )

            # Collect all their output files
            files = self._get_geoclipsequence_output_files(node, start, end)

            # Check if the layer is an explicit save layer, because if it is
            # then likely it is collected as its own instance by the
            # CollectUsdLayers plug-in and we want to attach the files to that
            # layer instance instead.
            target_instance = instance
            if info_prim.customData.get("HoudiniSaveControl") == "Explicit":
                override_instance = self._find_instance_by_explict_save_layer(
                    instance,
                    layer
                )
                if override_instance:
                    target_instance = override_instance

            # Set up transfers
            transfers = target_instance.data.setdefault("transfers", [])
            resources_dir = target_instance.data["resourcesDir"]
            resources_dir_name = os.path.basename(resources_dir)
            for src in files:
                # Make relative transfers of these files and remap
                # them to relative paths from the published USD layer
                src_name = os.path.basename(src)
                transfers.append(
                    (src, os.path.join(resources_dir, src_name))
                )

                asset_remap[src] = f"./{resources_dir_name}/{src_name}"

                self.log.debug(
                    "Registering transfer & remap: "
                    f"{src} -> {asset_remap[src]}"
                )

    def _get_geoclipsequence_output_files(
        self, clip_node: hou.Node, start: int, end: int
    ) -> list[str]:
        """
        
        A Geometry Clip Sequence only writes out files for the frames that
        appear in the ROP render range. If it has a start and end frame, then
        it won't write out frames beyond those frame ranges. The clip start
        offset shifts the clip frame numbers from the render frame range, but
        it does not shift the start and end frames of the clip itself.
        
        As such, we find the intersection of the frame ranges to determine the
        files to be written out.
        
        Args:
            clip_node (hou.Node): The Geometry Clip Sequence node.
            start (int): The ROP render start frame.
            end (int): The ROP render end frame.

        Returns:
            list[str]: List of filepaths.
        """
        # TODO: We may want to process this node in the Context Options of the
        #  USD ROP to be correct in the case of e.g. multishot workflows
        # Collect the manifest and topology file
        files: list[str] = [
            clip_node.evalParm('manifestfile'),
            clip_node.evalParm('topologyfile')
        ]

        saveclipfilepath: str = \
            clip_node.parm('saveclipfilepath').evalAtFrame(start)

        frame_collection, _ = clique.assemble(
            [saveclipfilepath],
            patterns=[clique.PATTERNS["frames"]],
            minimum_items=1
        )

        # Skip if no frame pattern detected.
        if not frame_collection:
            self.log.warning(
                f"Unable detect frame sequence in filepath: {saveclipfilepath}"
            )
            # Assume it's some form of static clip file in this scenario
            files.append(saveclipfilepath)
            return files

        # Shift the render range by the clip start offset
        clip_start_offset: int = int(clip_node.evalParm('clipstartoffset'))
        start += clip_start_offset
        end += clip_start_offset

        # Collect the clip frames that fall within the render range
        # because those will the clip frames to be written out.
        frames = get_clip_frames_in_frame_range(
            clip_start=int(clip_node.evalParm('startframe')),
            clip_end=int(clip_node.evalParm('endframe')),
            has_end_set=bool(clip_node.evalParm('setendframe')),
            loop=bool(clip_node.evalParm('loopframes')),
            range_start=start,
            range_end=end
        )

        # It's always expected to be one collection.
        frame_collection = frame_collection[0]
        frame_collection.indexes.clear()
        frame_collection.indexes.update(frames)
        files.extend(list(frame_collection))
        return files

    def _find_instance_by_explict_save_layer(
        self,
        instance: pyblish.api.Instance,
        layer
    ) -> Optional[pyblish.api.Instance]:
        """Find the target instance (in context) for the given layer if it's
        an explicit save layer.

        If the layer is an explicit save layer, then try to find if there's a
        publish instance for it and return it instead. Otherwise, return the
        input instance.
        """
        for other_instance in instance.context:
            # Skip self
            if instance is other_instance:
                continue

            if other_instance.data.get("usd_layer") is layer:
                self.log.debug(
                    "Setting explicit save layer target instance: "
                    f"{other_instance}"
                )
                return other_instance
        return None
