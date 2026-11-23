# -*- coding: utf-8 -*-
"""Prototype creator for the AYON File Cache SOP.

The AYON File Cache is a SOP HDA instead of a ROP, so this creator uses the
cache node itself as the publish instance node. The instance data keeps the
cache node path for the later collect/extract/publish phases.
"""
import hou

from ayon_core.pipeline import CreatedInstance, CreatorError

from ayon_houdini.api import plugin


FILE_CACHE_TYPE = "ayon::Sop/ayon_filecache::1.0"


class CreateFileCache(plugin.HoudiniCreator):
    """Create a publish instance for an AYON File Cache node."""

    identifier = "io.ayon.creators.houdini.filecache"
    label = "AYON File Cache"
    product_base_type = "filecache"
    product_type = product_base_type
    icon = "archive"
    description = "Publish an AYON File Cache SOP"

    def create(self, product_name, instance_data, pre_create_data):
        self.selected_nodes = hou.selectedNodes()

        cache_node = next(
            (
                node
                for node in self.selected_nodes
                if node.type().name() == FILE_CACHE_TYPE
            ),
            None,
        )
        if cache_node is None:
            raise CreatorError(
                "Select an AYON File Cache node before creating the instance."
            )

        instance_data["node_type"] = cache_node.type().name()
        instance_data["cache_node"] = cache_node.path()
        instance_data["instance_node"] = cache_node.path()
        instance_data["instance_id"] = cache_node.path()
        instance_data["families"] = self.get_publish_families()
        instance_data.setdefault("creator_attributes", {})

        instance = CreatedInstance(
            product_type=self.product_type,
            product_base_type=self.product_base_type,
            product_name=product_name,
            data=instance_data,
            creator=self,
        )

        self._add_instance_to_context(instance)
        self._imprint_instance(cache_node, instance)
        return instance

    def remove_instances(self, instances):
        """Remove publish metadata without deleting the artist's cache node."""
        for instance in instances:
            node = hou.node(instance.data.get("instance_node"))
            if node:
                parm_group = node.parmTemplateGroup()
                for parm in node.spareParms():
                    if (
                        parm.name() in {"id", "creator_identifier"}
                        or parm.name().startswith("AYON_")
                    ):
                        parm_group.remove(parm.name())
                node.setParmTemplateGroup(parm_group)
            self._remove_instance_from_context(instance)

    def _imprint_instance(self, node, instance):
        """Store instance data without colliding with HDA definition parms."""
        data = instance.data_to_store()
        for key, storage_key in (
            ("folderPath", "AYON_CACHE_FOLDER_PATH"),
            ("task", "AYON_CACHE_TASK"),
        ):
            value = data.pop(key, None)
            if value is not None:
                data[storage_key] = value
        self.imprint(node, data)

    def get_publish_families(self):
        return ["filecache", "cache"]

    def get_network_categories(self):
        return [
            hou.sopNodeTypeCategory(),
            hou.objNodeTypeCategory(),
        ]
