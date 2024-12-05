import os
import re

import hou
import pyblish.api

from ayon_houdini.api import plugin


class CollectArnoldROPRenderProducts(plugin.HoudiniInstancePlugin):
    """Collect Arnold ROP Render Products

    Collects the instance.data["files"] for the render products.

    Provides:
        instance    -> files

    """

    label = "Arnold ROP Render Products"
    # This specific order value is used so that
    # this plugin runs after CollectFrames
    order = pyblish.api.CollectorOrder + 0.11
    families = ["arnold_rop"]

    def process(self, instance):

        rop = hou.node(instance.data.get("instance_node"))

        default_prefix = self.evalParmNoFrame(rop, "ar_picture")
        render_products = []

        export_prefix = None
        export_products = []
        if instance.data["splitRender"]:
            export_prefix = self.evalParmNoFrame(
                rop, "ar_ass_file", pad_character="0"
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

        # Default beauty AOV
        beauty_product = self.get_render_product_name(prefix=default_prefix,
                                                      suffix=None)
        render_products.append(beauty_product)

        files_by_aov = {
            "": self.generate_expected_files(instance, beauty_product)
        }

        # Assume it's a multipartExr Render.
        multipartExr = True

        num_aovs = rop.evalParm("ar_aovs")

        for index in range(1, num_aovs + 1):
            
            aov_enabled = rop.evalParm("ar_enable_aov{}".format(index)) 
            aov_sep = rop.evalParm("ar_aov_separate{}".format(index))
            aov_path = rop.evalParm("ar_aov_separate_file{}".format(index))
            
            # Skip disabled AOVs or AOVs with no separate aov file path
            if not all((aov_enabled, aov_path, aov_sep)):
                continue

            if rop.evalParm("ar_aov_exr_enable_layer_name{}".format(index)):
                label = rop.evalParm("ar_aov_exr_layer_name{}".format(index))
            else:
                label = self.evalParmNoFrame(rop, "ar_aov_label{}".format(index))

            # NOTE:
            #  we don't collect the actual AOV path but rather assume 
            #    the user has used the default beauty path (collected above)
            #    with the AOV name before the extension.
            #  Also, Note that Ayon Publishing does not require a specific file name,
            #    as it will be renamed according to the naming conventions set in the publish template.
            aov_product = self.get_render_product_name(
                prefix=default_prefix, suffix=label
            )
            render_products.append(aov_product)
            files_by_aov[label] = self.generate_expected_files(instance,
                                                               aov_product)

            # Set to False as soon as we have a separated aov.
            multipartExr = False

        # Review Logic expects this key to exist and be True
        # if render is a multipart Exr.
        # As long as we have one AOV then multipartExr should be True.
        instance.data["multipartExr"] = multipartExr

        for product in render_products:
            self.log.debug("Found render product: {}".format(product))

        instance.data["files"] = list(render_products)

        # For now by default do NOT try to publish the rendered output
        instance.data["publishJobState"] = "Suspended"
        instance.data["attachTo"] = []      # stub required data

        if "expectedFiles" not in instance.data:
            instance.data["expectedFiles"] = list()
        instance.data["expectedFiles"].append(files_by_aov)

    def get_render_product_name(self, prefix, suffix):
        """Return the output filename using the AOV prefix and suffix"""

        # When AOV is explicitly defined in prefix we just swap it out
        # directly with the AOV suffix to embed it.
        # Note: ${AOV} seems to be evaluated in the parameter as %AOV%
        if "%AOV%" in prefix:
            # It seems that when some special separator characters are present
            # before the %AOV% token that Redshift will secretly remove it if
            # there is no suffix for the current product, for example:
            # foo_%AOV% -> foo.exr
            pattern = "%AOV%" if suffix else "[._-]?%AOV%"
            product_name = re.sub(pattern,
                                  suffix,
                                  prefix,
                                  flags=re.IGNORECASE)
        else:
            if suffix:
                # Add ".{suffix}" before the extension
                prefix_base, ext = os.path.splitext(prefix)
                product_name = prefix_base + "." + suffix + ext
            else:
                product_name = prefix

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
