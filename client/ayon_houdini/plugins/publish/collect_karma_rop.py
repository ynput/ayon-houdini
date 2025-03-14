import re
import os

import hou
import pyblish.api

from ayon_houdini.api.lib import evalParmNoFrame
from ayon_houdini.api import plugin


class CollectKarmaROPRenderProducts(plugin.HoudiniInstancePlugin):
    """Collect Karma Render Products

    Collects the instance.data["files"] for the multipart render product.

    Provides:
        instance    -> files

    """

    label = "Karma ROP Render Products"
    # This specific order value is used so that
    # this plugin runs after CollectFrames
    order = pyblish.api.CollectorOrder + 0.11
    families = ["karma_rop"]

    def process(self, instance):

        rop = hou.node(instance.data.get("instance_node"))

        default_prefix = evalParmNoFrame(rop, "picture")
        render_products = []

        # Default beauty AOV
        beauty_product = self.get_render_product_name(
            prefix=default_prefix, suffix=None
        )
        render_products.append(beauty_product)

        files_by_aov = {
            "beauty": self.generate_expected_files(instance,
                                                   beauty_product)
        }

        # Review Logic expects this key to exist and be True
        # if render is a multipart Exr.
        # As long as we have one AOV then multipartExr should be True.
        # By default karma render is a multipart Exr.
        instance.data["multipartExr"] = True

        filenames = list(render_products)
        instance.data["files"] = filenames

        for product in render_products:
            self.log.debug("Found render product: %s" % product)

        if "expectedFiles" not in instance.data:
            instance.data["expectedFiles"] = list()
        instance.data["expectedFiles"].append(files_by_aov)

    def get_render_product_name(self, prefix, suffix):
        product_name = prefix
        if suffix:
            # Add ".{suffix}" before the extension
            prefix_base, ext = os.path.splitext(prefix)
            product_name = "{}.{}{}".format(prefix_base, suffix, ext)

        return product_name

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
