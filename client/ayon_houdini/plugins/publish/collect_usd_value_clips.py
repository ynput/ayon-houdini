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

        # Houdini LOPs only allows one geoclip. anynewer geoclip overrides the previous one.
        clip_node = None
        for node_id in editor_nodes:
            node = hou.nodeBySessionId(node_id)
            if node.type().name() == "geoclipsequence":
                clip_node = node
                break

        if clip_node is None:
            return

        files = []
        files.append(clip_node.evalParm('manifestfile'))
        files.append(clip_node.evalParm('topologyfile'))

        # Number of frames: 

        start_frame = int(clip_node.evalParm('startframe'))

        loop_frames = 1 - clip_node.evalParm('loopframes')
        end_frame = int(clip_node.evalParm('endframe') + loop_frames)


        saveclipfilepath = clip_node.parm('saveclipfilepath').evalAtFrame(start_frame)

        frame_collection, _ = clique.assemble(
            [saveclipfilepath],
            patterns=[clique.PATTERNS["frames"]],
            minimum_items=1
        )

        # Return as no frame pattern detected.
        if not frame_collection:
            return
            
        # It's always expected to be one collection.
        frame_collection = frame_collection[0]
        frame_collection.indexes.clear()
        frame_collection.indexes.update(
            list(range(start_frame, end_frame + 1))
        )
        files.extend(list(frame_collection))

        # Register Files for transfer and remap them.
        transfers = instance.data.setdefault("transfers", [])
        asset_remap = instance.data.setdefault("assetRemap", {})

        resources_dir = instance.data["resourcesDir"]
        resources_dir_name = os.path.basename(resources_dir)

        for src in files:
            src_name = os.path.basename(src)

            transfers.append(
                (src, os.path.join(resources_dir, src_name))
            )

            asset_remap[src] = f"./{resources_dir_name}/{src_name}"

            self.log.debug(f"Registering transfer & remap: {src} -> {asset_remap[src]}")
