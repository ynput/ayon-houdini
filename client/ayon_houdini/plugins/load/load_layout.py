from __future__ import annotations
import json
import collections
from typing import Any, Optional, List

import ayon_api

from ayon_houdini.api import plugin, pipeline

from ayon_core.pipeline.load import (
    get_representation_contexts,
    get_loaders_by_name,
    load_with_repre_context,
    LoadError
)

import hou

MEMBER_ATTR_NAME = "AYON_layout_members"


class LayoutLoader(plugin.HoudiniLoader):
    """Layout Loader (json)"""

    product_types = {"layout"}
    representations = {"json"}

    label = "Load Layout"
    order = -10
    icon = "code-fork"
    color = "orange"

    # For JSON elements where we don't know what representation
    # to use, prefer to load the representation in this order.
    repre_order_by_name: dict[str, int] = {
        key: i for i, key in enumerate([
            "fbx", "abc", "usd", "vdb", "bgeo"
        ])
    }
    # Settings
    remove_layout_container_members = False

    def _get_repre_contexts_by_version_id(
        self,
        data: dict,
        context: dict
    ) -> dict[str, list[dict[str, dict]]]:
        """Fetch all representation contexts for all version ids in data
        at once - as optimal query."""
        version_ids = {
            element.get("version")
            for element in data
        }
        version_ids.discard(None)
        if not version_ids:
            return {}

        output = collections.defaultdict(list)
        project_name: str = context["project"]["name"]
        repre_entities = ayon_api.get_representations(
            project_name,
            version_ids=version_ids
        )
        repre_contexts = get_representation_contexts(
            project_name,
            repre_entities
        )
        for repre_context in repre_contexts.values():
            version_id = repre_context["version"]["id"]
            output[version_id].append(repre_context)
        return dict(output)

    @staticmethod
    def _get_loader_name(product_type: str, extension: str) -> Optional[str]:
        """_summary_

        Args:
            product_type (str): The type of the product.
            extension (str): The file extension of the product.

        Raises:
            LoadError: If the product type or extension is not supported.

        Returns:
            Optional[str]: The name of the loader plugin, or None if not found.
        """
        if product_type in {
            "model", "animation", "pointcache", "gpuCache"
        }:
            if extension == "abc":
                return "AbcLoader"
            elif extension == "fbx":
                return "FbxLoader"
            else:
                raise LoadError(
                    f"Unsupported extension '{extension}' "
                    f"for product type '{product_type}'"
                )
        elif product_type == "vdbcache":
            return "VdbLoader"

        return None

    def _process_element(
        self,
        element: dict[str, Any],
        repre_contexts_by_version_id: dict[str, list[dict]]
    ) -> list[str]:
        """Load one of the elements from a layout JSON file.

        Each element will specify a version for which we will load
        the first representation.
        """
        version_id = element.get("version")
        if not version_id:
            self.log.warning(
                f"No version id found in element: {element}")
            return []

        repre_contexts: list[dict] = repre_contexts_by_version_id.get(
            version_id, []
        )
        if not repre_contexts:
            self.log.error(
                "No representations found for version id:"
                f" {version_id}")
            return []

        def _sort_by_preferred_order(_repre_context: dict) -> int:
            _repre_name: str = _repre_context["representation"]["name"]
            return self.repre_order_by_name.get(
                _repre_name,
                len(self.repre_order_by_name) + 1
            )

        repre_contexts.sort(key=_sort_by_preferred_order)

        product_type = element.get("product_type")
        extension = element.get("extension", "")
        if product_type is None:
            # Backwards compatibility
            product_type = element.get("family")
        loader_name = self._get_loader_name(product_type, extension)
        # Find loader plugin
        # TODO: Cache the loaders by name once
        loader = get_loaders_by_name().get(loader_name, None)
        if not loader:
            self.log.error(
                f"No valid loader '{loader_name}' found for: {element}"
            )
            return []

        # Find a matching representation for the loader among
        # the ordered representations of the version
        # TODO: We should actually figure out from the published data what
        #   representation is actually preferred instead of guessing
        #   a first entry that is compatible with the loader
        supported_repre_context: Optional[dict[str, dict[str, Any]]] = None
        for repre_context in repre_contexts:
            if loader.is_compatible_loader(repre_context):
                supported_repre_context = repre_context

        if not supported_repre_context:
            self.log.error(
                f"Loader '{loader_name}' does not support"
                f" representation contexts: {repre_contexts}"
            )
            return []

        # Load the representation
        # TODO: Currently load API does not enforce a return data structure
        #  from the `Loader.load` call. In Maya ReferenceLoader may return
        #  a list of container nodes (objectSet names) but others may return a
        #  single container node.
        instance_name: str = element['instance_name']
        result = load_with_repre_context(
            loader,
            repre_context=supported_repre_context,
            namespace=instance_name
        )
        self.log.info(f"Loaded element with loader '{loader_name}': {result}")
        if isinstance(result, hou.Node):
            containers: list[hou.node] = [result]
        elif isinstance(result, list):
            containers: list[hou.node] = result
        else:
            self.log.warning(
                f"Loader {loader} returned invalid container data: {result}"
            )
            return []

        # Move the container root node
        for container in containers:
            self.set_transformation(container, element)
        return containers

    def set_transformation(self, container, element):
        """Set the transformation of the container root node based on the
        element data.

        Args:
            container (str): container node name.
            element (dict[str, Any]): element data from layout json
        """
        hou_transform_matrix = element["transform_matrix"]
        self._set_transformation_by_matrix(container,
                                           hou_transform_matrix)
        instance_name = element["instance_name"]
        for object_data in element.get("object_transform", []):
            for obj_name, transform_matrix in object_data.items():
                expected_name: str = f"{instance_name}:{obj_name}*"
                # TODO: support different networks
                obj_root = hou.node("/obj").glob(expected_name)
                if not obj_root:
                    self.log.warning(
                        f"No transforms found for: {expected_name}"
                    )
                    continue
                self._set_transformation_by_matrix(
                    obj_root,
                    transform_matrix
                )

    def _set_transformation_by_matrix(self, node, matrix):
        """Set the transformation of a node based on a 4x4
        transformation matrix.

        Args:
            node (str): node name.
            matrix (list): 4x4 transformation matrix as a flat
                list of 16 floats.
        """
        hou_matrix = hou.Matrix4(matrix)
        node.setParmTransform(hou_matrix)

    def load(self, context, name=None, namespace=None, data=None):
        obj = hou.node("/obj")
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        subset_node = obj.createNode("subnet", node_name=node_name)
        subset_node.moveToGoodPosition()

        path = self.filepath_from_context(context)
        self.log.info(f">>> loading json [ {path} ]")
        with open(path, "r") as fp:
            data = json.load(fp)

        # get the list of representations by using version id
        repre_contexts_by_version_id = self._get_repre_contexts_by_version_id(
            data, context
        )
        container_members: list[hou.Node] = []
        for element in data:
            loaded_containers = self._process_element(
                element,
                repre_contexts_by_version_id
            )
            container_members.extend(loaded_containers)

        self[:] = [subset_node]

        container = pipeline.containerise(
            node_name,
            namespace,
            [subset_node],
            context,
            self.__class__.__name__,
            suffix=""
        )
        self._set_members(container, container_members)

        return container

    def update(self, container, context):
        repre_entity = context["representation"]
        path = self.filepath_from_context(context)
        self.log.info(f">>> loading json [ {path} ]")
        with open(path, "r") as fp:
            data = json.load(fp)

        # get the list of representations by using version id
        repre_contexts_by_version_id = self._get_repre_contexts_by_version_id(
            data, context
        )
        member_containers = self._get_members(container["node"])
        updated_containers: list[hou.Node] = []
        for element in data:
            # Find a matching container node among the members
            # TODO: Make this lookup more reliable than just
            #  checking the container node name.
            instance_name: str = element.get("instance_name")
            update_containers: list[hou.Node] = [
                node for node in member_containers
                if instance_name in node.name()
            ]
            if update_containers:
                # Update existing elements
                for update_container in update_containers:
                    self.set_transformation(update_container, element)
            else:
                # Load new elements and add them to container
                loaded_containers: list[hou.Node] = self._process_element(
                    element, repre_contexts_by_version_id
                )
                updated_containers.extend(loaded_containers)

        container_node = container["node"]
        self._set_members(container_node, updated_containers)
        container_node.setParms({
            "filepath": self.filepath_from_context(context),
            "representation": str(repre_entity["id"])
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container) -> None:
        node = container["node"]
        if self.remove_layout_container_members:
            members = self._get_members(node)
            for member in members:
                member.destroy()
        node.destroy()

    def _get_members(self, node: hou.OpNode) -> List[hou.OpNode]:
        """Get the member nodes of the layout container.

        Args:
            node (hou.OpNode): The node representing the layout container.

        Returns:
            List[hou.OpNode]: The list of member nodes of the layout container.
        """
        return node.parm(MEMBER_ATTR_NAME).evalAsNodes()

    def _set_members(self, node: hou.OpNode, members: List[hou.OpNode]):
        """Set the member nodes of the layout container.

        Args:
            node (hou.OpNode): The node representing the layout container.
            members (List[hou.OpNode]): The list of member nodes to set.
        """
        # Add/set a parm of type node operator list
        parm = node.parm(MEMBER_ATTR_NAME)
        if not parm:
            # Add parm
            parm_template = hou.StringParmTemplate(
                name=MEMBER_ATTR_NAME ,
                label="Layout Members",
                num_components=1,
                string_type=hou.stringParmType.NodeReferenceList,
                # only OBJ nodes
                # tags={"opfilter": "!!OBJ!!", "oprelative": "."}
            )
            parm_template_group = node.parmTemplateGroup()
            parm_template_group.append(parm_template)
            node.setParmTemplateGroup(parm_template_group)
            parm = node.parm(MEMBER_ATTR_NAME)

        # Set value
        nodes_str = " ".join(node.path() for node in members)
        parm.set(nodes_str)
