# -*- coding: utf-8 -*-
import inspect
import json
import os

import hou
import pyblish.api
from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectROPAction


class ValidateUSDRenderTiles(plugin.HoudiniInstancePlugin,
                             OptionalPyblishPluginMixin):
    """Validate a USD Render ROP that renders tiles.

    With Tiled Render on, husk renders the image in tiles that are then
    stitched: by husk itself with Render All Tiles and Stitch Final Image
    (autotile), else by a farm job with `itilestitch`. Both place each tile
    by its EXR data window and denoise each tile on its own, so the outputs
    must be EXR and the denoiser off. Without autotile, rendering the ROP
    itself only renders its own tile index, so a split farm render is
    needed.
    """

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render Tiles"
    actions = [SelectROPAction]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        rop = hou.node(instance.data["instance_node"])
        if not rop.evalParm("husk_tile"):
            return

        creator_attributes = instance.data.get("creator_attributes", {})
        if creator_attributes.get("render_target") == "local_no_render":
            # Nothing is rendered.
            return

        invalid = []
        autotile_parm = rop.parm("husk_autotile")
        # The ROP has no autotile parm before Houdini 21.
        autotile = autotile_parm and autotile_parm.eval()
        if not autotile and not instance.data.get("splitRender"):
            invalid.append(
                "Only tile {} would be rendered: turn on Render All Tiles "
                "and Stitch Final Image, or use a split farm render "
                "target.".format(rop.evalParm("husk_tileindex"))
            )

        for filepath in instance.data.get("files", []):
            if os.path.splitext(filepath)[1].lower() != ".exr":
                invalid.append(
                    "Tiles need EXR files, other formats stitch into a "
                    "wrong image: {}".format(filepath)
                )

        render_settings = instance.data.get("rendersettings")
        if render_settings:
            # Karma's image filters: a JSON list of [name, options].
            attr = render_settings.GetPrim().GetAttribute(
                "karma:global:imagefilter")
            filters = json.loads(attr.Get() or "[]") if attr else []
            if any(name == "denoise" for name, _ in filters):
                invalid.append(
                    "The denoiser runs on each tile on its own: turn it off "
                    "on {}.".format(render_settings.GetPath())
                )

        if invalid:
            for message in invalid:
                self.log.error(message)
            raise PublishValidationError(
                "Tiled Render settings are invalid.",
                title=self.label,
                description=self.get_description()
            )

    def get_description(self):
        return inspect.cleandoc(
            """### Invalid tiled render

            The USD Render ROP has **Tiled Render** on. The tiles render in
            one of two ways:

            - With **Render All Tiles and Stitch Final Image** (Houdini
              21+), husk renders every tile and stitches them in one
              process, locally or on the farm.
            - Without it, each tile is a render of its own, which only the
              farm runs: set the render target to **Farm Export & Farm
              Rendering** or **Local Export & Farm Rendering**. Any other
              target only renders the tile set in **Index**.

            In both ways:

            - Render to EXR files. Other formats have no data window, so
              each tile is written full size, black outside the tile, and
              the stitched image comes out wrong without an error.
            - Turn off the denoiser (Karma Render Settings, **Image Output >
              Filters > Image Filters > Denoiser**). It denoises each tile
              on its own, so the image changes near the tile edges.
            """
        )
