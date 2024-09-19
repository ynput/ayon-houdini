from ayon_houdini.api import plugin, colorspace

import pyblish.api


class CollectHoudiniRenderColorspace(plugin.HoudiniInstancePlugin):
    """Collect Colorspace data for render output images.

    This currently assumes that all render products are in 'scene_linear'
    colorspace role - which is the default behavior for renderers in Houdini.
    """

    label = "Collect Render Colorspace"
    order = pyblish.api.CollectorOrder + 0.15
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender"]

    def process(self, instance):
        # Set the required data for `ayon_core.pipeline.farm.pyblish_functions`
        # functions used for farm publish job processing.

        # Define render products for `create_instances_for_aov`
        # which uses it in `_create_instances_for_aov()` to match the render
        # product's name to aovs to define the colorspace.
        expected_files = instance.data.get("expectedFiles")
        if not expected_files:
            self.log.debug("No expected files found. "
                           "Skipping collecting of render colorspace.")
            return
        aov_name = list(expected_files[0].keys())
        render_products_data = colorspace.ARenderProduct(aov_name)
        instance.data["renderProducts"] = render_products_data

        # Required data for `create_instances_for_aov`
        colorspace_data = colorspace.get_color_management_preferences()
        instance.data["colorspaceConfig"] = colorspace_data["config"]
        instance.data["colorspaceDisplay"] = colorspace_data["display"]
        instance.data["colorspaceView"] = colorspace_data["view"]

        # Used in `create_skeleton_instance()`
        instance.data["colorspace"] = colorspace.get_scene_linear_colorspace()
