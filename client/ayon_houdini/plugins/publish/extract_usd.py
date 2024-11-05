import os
from typing import List, AnyStr

import pyblish.api

from ayon_core.pipeline.entity_uri import construct_ayon_entity_uri
from ayon_core.pipeline.publish.lib import get_instance_expected_output_path
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import render_rop
from ayon_houdini.api.usd import remap_paths

import hou


class ExtractUSD(plugin.HoudiniExtractorPlugin):

    order = pyblish.api.ExtractorOrder
    label = "Extract USD"
    families = ["usdrop"]

    use_ayon_entity_uri = False

    def process(self, instance):

        ropnode = hou.node(instance.data.get("instance_node"))

        # Get the filename from the filename parameter
        output = ropnode.evalParm("lopoutput")
        staging_dir = os.path.dirname(output)
        instance.data["stagingDir"] = staging_dir
        file_name = os.path.basename(output)

        self.log.info("Writing USD '%s' to '%s'" % (file_name, staging_dir))

        mapping = self.get_source_to_publish_paths(instance.context)
        if mapping:
            self.log.debug(f"Remapping paths: {mapping}")

        # Allow instance-specific path remapping overrides, e.g. changing
        # paths on used resources/textures for looks
        instance_mapping = instance.data.get("assetRemap", {})
        if instance_mapping:
            self.log.debug("Instance-specific asset path remapping:\n"
                           f"{instance_mapping}")
        mapping.update(instance_mapping)

        with remap_paths(ropnode, mapping):
            render_rop(ropnode)

        assert os.path.exists(output), "Output does not exist: %s" % output

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'usd',
            'ext': 'usd',
            'files': file_name,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)

    def get_source_to_publish_paths(self,
                                    context):
        """Define a mapping of all current instances in context from source
        file to publish file so this can be used on the USD save to remap
        asset layer paths on publish via AyonRemapPaths output processor

        Arguments:
            context (pyblish.api.Context): Publish context.

        Returns:
            dict[str, str]: Mapping from source path to remapped path.

        """

        mapping = {}
        for instance in context:
            if not instance.data.get("active", True):
                continue

            if not instance.data.get("publish", True):
                continue

            for repre in instance.data.get("representations", []):
                name = repre.get("name")
                ext = repre.get("ext")

                # TODO: The remapping might need to get more involved if the
                #   asset paths that are set use e.g. $F
                # TODO: If the representation has multiple files we might need
                #   to define the path remapping per file of the sequence
                if self.use_ayon_entity_uri:
                    # Construct AYON entity URI
                    # Note: entity does not exist yet
                    path = construct_ayon_entity_uri(
                        project_name=context.data["projectName"],
                        folder_path=instance.data["folderPath"],
                        product=instance.data["productName"],
                        version=instance.data["version"],
                        representation_name=name
                    )
                else:
                    # Resolved publish filepath
                    path = get_instance_expected_output_path(
                        instance, representation_name=name, ext=ext
                    )

                for source_path in get_source_paths(instance, repre):
                    source_path = os.path.normpath(source_path)
                    mapping[source_path] = path

        return mapping


def get_source_paths(
        instance: pyblish.api.Instance,
        repre: dict
) -> List[AnyStr]:
    """Return the full source filepaths for an instance's representations"""

    staging = repre.get("stagingDir", instance.data.get("stagingDir"))

    # Support special `files_raw` key for representations that may originate
    # from a path in the USD file including `:SDF_FORMAT_ARGS:` which we will
    # also want to match against.
    if "files_raw" in repre:
        files = repre["files_raw"]
    else:
        files = repre.get("files", [])

    if isinstance(files, list):
        return [os.path.join(staging, fname) for fname in files]
    elif isinstance(files, str):
        # Single file
        return [os.path.join(staging, files)]

    raise TypeError(f"Unsupported type for representation files: {files} "
                    "(supports list or str)")
