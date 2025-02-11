import re
import os

import hou
import pyblish.api

from ayon_houdini.api.lib import evalParmNoFrame
from ayon_houdini.api import plugin


class CollectVrayROPRenderProducts(plugin.HoudiniInstancePlugin):
    """Collect Vray Render Products

    Collects the instance.data["files"] for the render products.

    Provides:
        instance    -> files

    """

    label = "VRay ROP Render Products"
    # This specific order value is used so that
    # this plugin runs after CollectFrames
    order = pyblish.api.CollectorOrder + 0.11
    families = ["vray_rop"]

    def process(self, instance):

        rop = hou.node(instance.data.get("instance_node"))

        default_prefix = evalParmNoFrame(rop, "SettingsOutput_img_file_path")
        render_products = []
        # TODO: add render elements if render element

        export_prefix = None
        export_products = []
        if instance.data["splitRender"]:
            export_prefix = evalParmNoFrame(
                rop, "render_export_filepath", pad_character="0"
            )
            beauty_export_product = self.get_render_product_name(
                prefix=export_prefix,
                suffix=None)
            export_products.append(beauty_export_product)
            self.log.debug(
                "Found export product: {}".format(beauty_export_product)
            )
            instance.data["ifdFile"] = beauty_export_product
            instance.data["exportFiles"] = list(export_products)

        beauty_product = self.get_render_product_name(default_prefix)
        render_products.append(beauty_product)
        files_by_aov = {
            "": self.generate_expected_files(instance,
                                                      beauty_product)}

        # Assume it's a multipartExr Render.
        multipartExr = True

        if instance.data.get("RenderElement", True):
            render_element = self.get_render_element_name(rop, default_prefix)
            if render_element:
                for aov, renderpass in render_element.items():
                    render_products.append(renderpass)
                    files_by_aov[aov] = self.generate_expected_files(
                        instance, renderpass)
                    # Set to False as soon as we have a separated aov.
                    multipartExr = False

        # Review Logic expects this key to exist and be True
        # if render is a multipart Exr.
        # As long as we have one AOV then multipartExr should be True.
        instance.data["multipartExr"] = multipartExr

        for product in render_products:
            self.log.debug("Found render product: %s" % product)
        filenames = list(render_products)
        instance.data["files"] = filenames

        # For now by default do NOT try to publish the rendered output
        instance.data["publishJobState"] = "Suspended"
        instance.data["attachTo"] = []      # stub required data

        if "expectedFiles" not in instance.data:
            instance.data["expectedFiles"] = list()
        instance.data["expectedFiles"].append(files_by_aov)
        self.log.debug("expectedFiles:{}".format(files_by_aov))

    def get_render_product_name(self, prefix, suffix="<reName>"):
        """Return the beauty output filename if render element enabled
        """
        # Remove aov suffix from the product: `prefix.aov_suffix` -> `prefix`
        aov_parm = ".{}".format(suffix)
        return prefix.replace(aov_parm, "")

    def get_render_element_name(self, node, prefix, suffix="<reName>"):
        """Return the output filename using the AOV prefix and suffix
        """
        render_element_dict = {}
        # need a rewrite
        re_path = node.evalParm("render_network_render_channels")
        if re_path:
            node_children = hou.node(re_path).children()
            for element in node_children:
                if element.shaderName() != "vray:SettingsRenderChannels":
                    aov = str(element)
                    render_product = prefix.replace(suffix, aov)
                    render_element_dict[aov] = render_product
        return render_element_dict

    def generate_expected_files(self, instance, path):
        """Create expected files in instance data"""

        dir = os.path.dirname(path)
        file = os.path.basename(path)

        if "#" in file:
            def replace(match):
                return "%0{}d".format(len(match.group()))

            file = re.sub("#+", replace, file)

        if "%" not in file:
            return path

        expected_files = []
        start = instance.data["frameStartHandle"]
        end = instance.data["frameEndHandle"]

        for i in range(int(start), (int(end) + 1)):
            expected_files.append(
                os.path.join(dir, (file % i)).replace("\\", "/"))

        return expected_files
