import copy
import os
import re

import pyblish.api

from ayon_core.pipeline import KnownPublishError
from ayon_core.pipeline.create import get_product_name
from ayon_houdini.api import plugin
import ayon_houdini.api.usd as usdlib

from pxr import Sdf
import hou


def copy_instance_data(instance_src, instance_dest, attr):
    """Copy instance data from `src` instance to `dest` instance.

    Examples:
        >>> copy_instance_data(instance_src, instance_dest,
        >>>                    attr="publish_attributes.CollectRopFrameRange")

    Arguments:
        instance_src (pyblish.api.Instance): Source instance to copy from
        instance_dest (pyblish.api.Instance): Target instance to copy to
        attr (str): Attribute on the source instance to copy. This can be
            a nested key joined by `.` to only copy sub entries of dictionaries
            in the source instance's data.

    Raises:
        KnownPublishError: If a parent key already exists on the destination
            instance but is not of the correct type (= is not a dict)

    """

    src_data = instance_src.data
    dest_data = instance_dest.data
    keys = attr.split(".")
    for i, key in enumerate(keys):
        if key not in src_data:
            break

        src_value = src_data[key]
        if i != len(key):
            dest_data = dest_data.setdefault(key, {})
            if not isinstance(dest_data, dict):
                raise KnownPublishError("Destination must be a dict.")
            src_data = src_value
        else:
            # Last iteration - assign the value
            dest_data[key] = copy.deepcopy(src_value)


class CollectUsdLayers(plugin.HoudiniInstancePlugin):
    """Collect the USD Layers that have configured save paths."""

    order = pyblish.api.CollectorOrder + 0.25
    label = "Collect USD Layers"
    families = ["usdrop"]

    def process(self, instance):
        # TODO: Replace this with a Hidden Creator so we collect these BEFORE
        #   starting the publish so the user sees them before publishing
        #   - however user should not be able to individually enable/disable
        #   this from the main ROP its created from?

        output = instance.data.get("output_node")
        if not output:
            self.log.debug("No output node found..")
            return

        rop_node = hou.node(instance.data["instance_node"])
        lop_path = rop_node.evalParm("loppath")
        lop_node = hou.node(lop_path)

        self.log.debug(f"ROP Node: {rop_node.path()} references LOP Node: {lop_node.path()}")

        def find_geoclipsequence(node):
            if node.type().name() == "geoclipsequence":
                return node
            for input_node in node.inputs():
                if input_node:
                    result = find_geoclipsequence(input_node)
                    if result:
                        return result
            return None

        geoclip_node = find_geoclipsequence(lop_node)
        self.log.debug(f" geoclip node {geoclip_node}")

        if geoclip_node:
            self.log.debug("True geoclip node")
            if geoclip_node.parm("saveclipfilepath"):
                clip_path = geoclip_node.evalParm("saveclipfilepath")
            else:
                clip_path = None
            manifest_path = geoclip_node.evalParm("manifestfile")
            topology_path = geoclip_node.evalParm("topologyfile")

            self.log.debug(f"Found GeoClipSequence Node: {geoclip_node.path()}")
            self.log.debug(f"Clip Path: {clip_path}")
            self.log.debug(f"Manifest Path: {manifest_path}")
            self.log.debug(f"Topology Path: {topology_path}")
        else: 
            self.log.debug("False not a geoclipsequence node")

        save_layers = []
        for layer in usdlib.get_configured_save_layers(rop_node):

            info = layer.rootPrims.get("HoudiniLayerInfo")
            save_path = info.customData.get("HoudiniSavePath")
            creator = info.customData.get("HoudiniCreatorNode")

            self.log.debug("Found configured save path: "
                           "%s -> %s", layer, save_path)

            # Log node that configured this save path
            creator_node = hou.nodeBySessionId(creator) if creator else None
            if creator_node:
                self.log.debug(
                    "Created by: %s", creator_node.path()
                )

            save_layers.append((layer,clip_path, manifest_path, save_path, creator_node))
        self.log.debug(f"save layers {save_layers}")
        # Store on the instance
        instance.data["usdConfiguredSavePaths"] = save_layers

        # Create configured layer instances so User can disable updating
        # specific configured layers for publishing.
        context = instance.context
        for layer, clip_path, manifest_path, save_path, creator_node in save_layers:
            name = os.path.basename(save_path)
            layer_inst = context.create_instance(name)

            # include same USD ROP
            layer_inst.append(rop_node)

            staging_dir, fname_with_args = os.path.split(save_path)

            # The save path may include :SDF_FORMAT_ARGS: which will conflict
            # with how we end up integrating these files because those will
            # NOT be included in the actual output filename on disk, so we
            # remove the SDF_FORMAT_ARGS from the filename.
            fname = Sdf.Layer.SplitIdentifier(fname_with_args)[0]
            fname_no_ext, ext = os.path.splitext(fname)

            variant = fname_no_ext

            # Strip off any trailing version number in the form of _v[0-9]+
            variant = re.sub("_v[0-9]+$", "", variant)

            layer_inst.data["usd_layer"] = layer
            layer_inst.data["usd_layer_save_path"] = save_path

            project_name = context.data["projectName"]
            variant_base = instance.data["variant"]
            product_name = get_product_name(
                project_name=project_name,
                # TODO: This should use task from `instance`
                task_name=context.data["anatomyData"]["task"]["name"],
                task_type=context.data["anatomyData"]["task"]["type"],
                host_name=context.data["hostName"],
                product_type="usd",
                variant=variant_base + "_" + variant,
                project_settings=context.data["project_settings"]
            )

            label = "{0} -> {1}".format(instance.data["name"], product_name)
            family = "usd"
            layer_inst.data["family"] = family
            layer_inst.data["families"] = [family]
            layer_inst.data["productName"] = product_name
            layer_inst.data["productType"] = instance.data["productType"]
            layer_inst.data["label"] = label
            layer_inst.data["folderPath"] = instance.data["folderPath"]
            layer_inst.data["task"] = instance.data.get("task")
            layer_inst.data["instance_node"] = instance.data["instance_node"]
            layer_inst.data["render"] = False
            layer_inst.data["output_node"] = creator_node

            # Inherit "use handles" from the source instance
            # TODO: Do we want to maybe copy full `publish_attributes` instead?
            copy_instance_data(
                instance, layer_inst,
                attr="publish_attributes.CollectRopFrameRange.use_handles"
            )

            # Allow this product to be grouped into a USD Layer on creation
            layer_inst.data["productGroup"] = (
                instance.data.get("productGroup") or "USD Layer"
            )
            # For now just assume the representation will get published
            representation = {
                "name": "usd",
                "ext": ext.lstrip("."),
                "stagingDir": staging_dir,
                "files": fname,

                # Store an additional key with filenames including the
                # SDF_FORMAT_ARGS so we can use this to remap paths
                # accurately later.
                "files_raw": fname_with_args
            }
            layer_inst.data.setdefault("representations", []).append(
                representation)
