from typing import List

import attr
import hou
from ayon_houdini.api.lib import get_color_management_preferences
from ayon_core.pipeline.colorspace import (
    get_display_view_colorspace_name,
    get_ocio_config_colorspaces
)


@attr.s
class LayerMetadata(object):
    """Data class for Render Layer metadata."""
    products: "List[RenderProduct]" = attr.ib()


@attr.s
class RenderProduct(object):
    """Specific Render Product Parameter for submitting."""
    colorspace = attr.ib()                      # colorspace
    productName = attr.ib(default=None)


class ARenderProduct(object):
    """This is the minimal data structure required to get
    `ayon_core.pipeline.farm.pyblish_functions.create_instances_for_aov` to
    work with deadline addon's job submissions."""
    # TODO: The exact data structure should actually be defined in core for all
    #  addons to align.
    def __init__(self, aov_names: List[str]):
        colorspace = get_scene_linear_colorspace()
        products = [
            RenderProduct(colorspace=colorspace, productName=aov_name)
            for aov_name in aov_names
        ]
        self.layer_data = LayerMetadata(products=products)


def get_scene_linear_colorspace():
    """Return colorspace name for Houdini's OCIO config scene linear role.

    By default, renderers in Houdini render output images in the scene linear
    role colorspace.

    Returns:
        Optional[str]: The colorspace name for the 'scene_linear' role in
            the OCIO config Houdini is currently set to.
    """
    ocio_config_path = hou.Color.ocio_configPath()
    colorspaces = get_ocio_config_colorspaces(ocio_config_path)
    return colorspaces["roles"].get("scene_linear", {}).get("colorspace")


def get_default_display_view_colorspace():
    """Returns the colorspace attribute of the default (display, view) pair.

    It's used for 'ociocolorspace' parm in OpenGL Node."""

    prefs = get_color_management_preferences()
    return get_display_view_colorspace_name(
        config_path=prefs["config"],
        display=prefs["display"],
        view=prefs["view"]
    )
