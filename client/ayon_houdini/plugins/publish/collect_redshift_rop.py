import re
import os

import hou
import pyblish.api

from ayon_houdini.api.lib import evalParmNoFrame
from ayon_houdini.api import plugin


class CollectRedshiftROPRenderProducts(plugin.HoudiniInstancePlugin):
    """Collect USD Render Products

    Collects the instance.data["files"] for the render products.

    Provides:
        instance    -> files

    """

    label = "Redshift ROP Render Products"
    # This specific order value is used so that
    # this plugin runs after CollectFrames
    order = pyblish.api.CollectorOrder + 0.11
    families = ["redshift_rop"]

    def process(self, instance):
        rop = hou.node(instance.data.get("instance_node"))

        default_prefix = evalParmNoFrame(rop, "RS_outputFileNamePrefix")
        beauty_suffix = rop.evalParm("RS_outputBeautyAOVSuffix")

        export_products = []
        if instance.data["splitRender"]:
            export_prefix = evalParmNoFrame(
                rop, "RS_archive_file", pad_character="0"
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

        full_exr_mode = (rop.evalParm("RS_outputMultilayerMode") == "2")
        if full_exr_mode:
            # Ignore beauty suffix if full mode is enabled
            # As this is what the rop does.
            beauty_suffix = ""

        # Assume it's a multipartExr Render.
        multipartExr = True

        # Default beauty/main layer AOV
        beauty_product = self.get_render_product_name(
            prefix=default_prefix, suffix=beauty_suffix
        )
        render_products = [beauty_product]
        files_by_aov = {
            beauty_suffix: self.generate_expected_files(
                instance,
                beauty_product
            )
        }

        aovs_rop = rop.parm("RS_aovGetFromNode").evalAsNode()
        if aovs_rop:
            rop = aovs_rop

        num_aovs = 0
        if not rop.evalParm('RS_aovAllAOVsDisabled'):
            num_aovs = rop.evalParm("RS_aov")

        for index in range(num_aovs):
            i = index + 1

            # Skip disabled AOVs
            if not rop.evalParm(f"RS_aovEnable_{i}"):
                continue

            aov_suffix = rop.evalParm(f"RS_aovSuffix_{i}")
            aov_prefix = evalParmNoFrame(rop, f"RS_aovCustomPrefix_{i}")
            if not aov_prefix:
                aov_prefix = default_prefix

            if rop.parm(f"RS_aovID_{i}").evalAsString() == "CRYPTOMATTE" or \
                  not full_exr_mode:

                aov_product = self.get_render_product_name(
                    aov_prefix, aov_suffix
                )
                render_products.append(aov_product)

                files_by_aov[aov_suffix] = self.generate_expected_files(
                    instance,
                    aov_product
                )

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
            instance.data["expectedFiles"] = []
        instance.data["expectedFiles"].append(files_by_aov)

    def get_render_product_name(self, prefix, suffix):
        """Return the output filename using the AOV prefix and suffix"""

        # When AOV is explicitly defined in prefix we just swap it out
        # directly with the AOV suffix to embed it.
        # Note: '$AOV' seems to be evaluated in the parameter as '%AOV%'
        has_aov_in_prefix = "%AOV%" in prefix
        if has_aov_in_prefix:
            # It seems that when some special separator characters are present
            # before the %AOV% token that Redshift will secretly remove it if
            # there is no suffix for the current product, for example:
            # foo_%AOV% -> foo.exr
            pattern = "%AOV%" if suffix else "[._-]?%AOV%"
            product_name = re.sub(pattern, suffix, prefix, flags=re.IGNORECASE)
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
