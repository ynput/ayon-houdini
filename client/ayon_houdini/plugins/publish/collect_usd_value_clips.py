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

        stage = instance.data.get("stage", None)
        if stage is None:
            return

        prim = stage.GetPrimAtPath("/HoudiniLayerInfo")
        editor_nodes = prim.GetCustomDataByKey("HoudiniEditorNodes")

        transfers = instance.data.setdefault("transfers", [])
        asset_remap = instance.data.setdefault("assetRemap", {})
        resources_dir = instance.data["resourcesDir"]
        resources_dir_name = os.path.basename(resources_dir)

        clip_node = None
        for node_id in editor_nodes:
            node = hou.nodeBySessionId(node_id)
            if node.type().name() != "geoclipsequence":
                continue
            clip_node = node

            files = []
            files.append(clip_node.evalParm('manifestfile'))
            files.append(clip_node.evalParm('topologyfile'))

            # Compute number of frames
            start_frame = int(clip_node.evalParm('startframe'))

            loop_frames = 1 - clip_node.evalParm('loopframes')
            end_frame = int(clip_node.evalParm('endframe') + loop_frames)

            saveclipfilepath = \
                clip_node.parm('saveclipfilepath').evalAtFrame(start_frame)

            frame_collection, _ = clique.assemble(
                [saveclipfilepath],
                patterns=[clique.PATTERNS["frames"]],
                minimum_items=1
            )

            # Skip if no frame pattern detected.
            if not frame_collection:
                continue

            # It's always expected to be one collection.
            frame_collection = frame_collection[0]
            frame_collection.indexes.clear()
            frame_collection.indexes.update(
                list(range(start_frame, end_frame + 1))
            )
            files.extend(list(frame_collection))

            for src in files:
                src_name = os.path.basename(src)

                transfers.append(
                    (src, os.path.join(resources_dir, src_name))
                )

                asset_remap[src] = f"./{resources_dir_name}/{src_name}"

                self.log.debug(
                    "Registering transfer & remap: "
                    f"{src} -> {asset_remap[src]}"
                )
