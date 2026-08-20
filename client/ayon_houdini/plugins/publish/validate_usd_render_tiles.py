# -*- coding: utf-8 -*-
import inspect

import hou
import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


# Husk renderer plugin names for Karma. Read from rop.evalParm("renderer").
# Reference: hou.lop.availableRendererInfo()
KARMA_RENDERER_PLUGINS = {
    "BRAY_HdKarma",     # Karma CPU
    "BRAY_HdKarmaXPU",  # Karma XPU
}

FARM_RENDER_TARGETS = {
    "farm",
    "farm_split",
    "local_export_farm_render",
}


class ValidateUSDRenderTiles(plugin.HoudiniInstancePlugin):
    """Validate tile-rendering settings on USD Render ROP instances.

    Tile rendering uses Husk's --tile-index / --tile-count flags via the
    Husk Standalone Deadline plugin. This validator catches incompatible
    combinations before submission.
    """

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render Tile Rendering"
    actions = [SelectROPAction]

    def process(self, instance):
        creator_attrs = instance.data.get("creator_attributes", {})
        if not creator_attrs.get("tile_rendering"):
            return

        rop_node = hou.node(instance.data["instance_node"])
        invalid = False

        render_target = creator_attrs.get("render_target")
        if render_target not in FARM_RENDER_TARGETS:
            self.log.error(
                "Tile rendering requires a farm render target "
                "(farm / farm_split / local_export_farm_render). "
                "Current render target: %r",
                render_target,
            )
            invalid = True

        tiles_x = int(creator_attrs.get("tile_count_x", 0))
        tiles_y = int(creator_attrs.get("tile_count_y", 0))
        if tiles_x < 1 or tiles_y < 1:
            self.log.error(
                "Tile rendering needs tile_count_x >= 1 and tile_count_y "
                ">= 1 (got %s × %s).",
                tiles_x, tiles_y,
            )
            invalid = True
        elif tiles_x * tiles_y < 2:
            self.log.error(
                "Tile rendering needs at least 2 tiles total (got %s × %s "
                "= %s).",
                tiles_x, tiles_y, tiles_x * tiles_y,
            )
            invalid = True

        renderer = rop_node.evalParm("renderer")
        if renderer not in KARMA_RENDERER_PLUGINS:
            self.log.error(
                "Tile rendering is currently validated only for Karma "
                "(BRAY_HdKarma / BRAY_HdKarmaXPU). Current renderer: %r. "
                "Other Husk delegates may work but are not yet covered.",
                renderer,
            )
            invalid = True

        # Warnings (non-blocking).
        if rop_node.evalParm("husk_delegateprod"):
            self.log.warning(
                "Husk 'Delegate Products' is enabled while tiling is on. "
                "Per-tile delegated render products may collide. "
                "Consider disabling 'Delegate Products' on the USD Render "
                "ROP for tile renders."
            )

        tile_count = tiles_x * tiles_y
        lopoutput = rop_node.evalParm("lopoutput") or ""
        if "$F" not in lopoutput and tile_count >= 8:
            self.log.warning(
                "Single USD export (no $F in lopoutput) combined with a "
                "high tile count (%s) means every tile task reads the same "
                "USD file. This is fine but memory-heavy on the farm.",
                tile_count,
            )

        if invalid:
            raise PublishValidationError(
                "Invalid tile rendering configuration.",
                title="Invalid Tile Rendering",
                description=self.get_description(),
            )

    def get_description(self):
        return inspect.cleandoc(
            """### Tile rendering misconfigured

            Tile rendering for the USD Render ROP requires:

            - **Render target** set to one of *Farm*, *Farm Export & Farm
              Render*, or *Local Export & Farm Render*. Local-only renders
              cannot tile (there are no farm tasks to fan out across).
            - **Tiles X** and **Tiles Y** both >= 1, and their product >= 2.
            - **Renderer** = Karma CPU or Karma XPU. Other Husk delegates
              are not yet validated for tile rendering.

            Disable tile rendering or fix the settings above.
            """
        )
