import os
import hou
import clique

import pyblish.api

from ayon_houdini.api import plugin


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
        prim_spec = layer.GetPrimAtPath("/HoudiniLayerInfo")
        if not prim_spec:
            return

        editor_nodes = prim_spec.customData.get("HoudiniEditorNodes")
        if not editor_nodes:
            return

        transfers = instance.data.setdefault("transfers", [])
        asset_remap = instance.data.setdefault("assetRemap", {})
        resources_dir = instance.data["resourcesDir"]
        resources_dir_name = os.path.basename(resources_dir)

        for node_id in editor_nodes:
            # Consider only geoclipsequence nodes
            node = hou.nodeBySessionId(node_id)
            if node.type().name() != "geoclipsequence":
                continue

            self.log.debug(
                f"Collecting outputs for Geometry Clip Sequence: {node.path()}"
            )

            # Collect all their output files
            files = self._get_geoclipsequence_output_files(node)
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

    def _get_geoclipsequence_output_files(self, clip_node) -> list[str]:
        # TODO: We may want to process this node in the Context Options of the
        #  USD ROP to be correct in the case of e.g. multishot workflows
        # Collect the manifest and topology file
        files: list[str] = [
            clip_node.evalParm('manifestfile'),
            clip_node.evalParm('topologyfile')
        ]

        # Collect the individual clip frames
        # Compute number of frames
        start_frame: int = int(clip_node.evalParm('startframe'))
        loop_frames: int = 1 - clip_node.evalParm('loopframes')
        end_frame: int = int(clip_node.evalParm('endframe') + loop_frames)

        saveclipfilepath: str = \
            clip_node.parm('saveclipfilepath').evalAtFrame(start_frame)

        frame_collection, _ = clique.assemble(
            [saveclipfilepath],
            patterns=[clique.PATTERNS["frames"]],
            minimum_items=1
        )

        # Skip if no frame pattern detected.
        if not frame_collection:
            self.log.warning(
                "Unable detect frame sequence in filepath '{saveclipfilepath}'"
            )
            # Assume it's some form of static clip file in this scenario
            files.append(saveclipfilepath)
            return files

        # It's always expected to be one collection.
        frame_collection = frame_collection[0]
        frame_collection.indexes.clear()
        frame_collection.indexes.update(
            list(range(start_frame, end_frame + 1))
        )
        files.extend(list(frame_collection))
        return files
