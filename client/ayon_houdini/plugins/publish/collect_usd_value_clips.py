import os
import hou
import clique
from typing import Optional

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
        info_prim = layer.GetPrimAtPath("/HoudiniLayerInfo")
        if not info_prim:
            return

        editor_nodes = info_prim.customData.get("HoudiniEditorNodes")
        if not editor_nodes:
            return

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
            files = self._get_geoclipsequence_output_files(node)

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
                f"Unable detect frame sequence in filepath: {saveclipfilepath}"
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
