import json
import contextlib

from ayon_houdini.api import plugin, lib

import hou


@contextlib.contextmanager
def monkeypatch_attribute(obj, name, value):
    original_value = getattr(obj, name)
    try:
        setattr(obj, name, value)
        yield
    finally:
        setattr(obj, name, original_value)


class CreateAyonPublishROP(plugin.HoudiniCreator):
    """Creator plugin for creating publishes."""

    identifier = "io.ayon.creators.houdini.rop_publish"
    label = "AYON Publish"
    product_type = "rop_publish"  # TODO: Come up with better name
    icon = "cubes"
    description = "Create AYON publish ROP "

    node_type = "ayon_publish"

    def get_network_categories(self):
        return [hou.ropNodeTypeCategory()]

    def get_publish_families(self):
        return ["rop_publish"]

    def imprint(self, node, values, update=False):
        # Imprint the value onto existing attributes instead
        # of trying to force create them because the HDA already
        # contains the attributes
        for key, value in values.items():
            parm = node.parm(key)
            if parm:
                if isinstance(value, dict):
                    value = lib.JSON_PREFIX + json.dumps(value)
                parm.set(value)

    def read(self, node):
        # Explicitly read the attributes because the attributes are not
        # spare parms on this HDA
        attributes = [
            # Ordered by appearance in the UI
            "id",
            "productType",
            "active"
            "creator_identifier",
            "variant",
            "folderPath",
            "task",
            "creator_attributes",
            "publish_attributes",
        ]
        result = {}
        for attr in attributes:

            parm = node.parm(attr)
            if not parm:
                result[attr] = None
                continue
            value = parm.eval()
            if isinstance(value, str) and value.startswith(lib.JSON_PREFIX):
                value = json.loads(value[len(lib.JSON_PREFIX):])
            result[attr] = value

        # Creator attributes and publish attributes must be dict to avoid
        # bugs in publisher UI
        for key in ["creator_attributes", "publish_attributes"]:
            if not result[key]:
                result[key] = {}

        # Compute product name
        # TODO: Preferably we wouldn't need to monkeypatch this but have
        #  ayon-core automatically be able to update and re-compute the
        #  product name if a custom product type is set for the instance.
        folder_path: str = result["folderPath"]
        task_name: str = result["task"]
        product_type: str = result["productType"]
        with monkeypatch_attribute(self, "product_type", product_type):
            result["productName"] = self.get_product_name(
                self.create_context.get_current_project_name(),
                self.create_context.get_folder_entity(folder_path),
                self.create_context.get_task_entity(folder_path, task_name),
                variant=result["variant"],
            )

        return result
