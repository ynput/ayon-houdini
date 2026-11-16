import json
import contextlib

from ayon_core.lib import is_func_signature_supported
from ayon_houdini.api import plugin, lib, ayon_publish

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
    """Creator plugin for creating publishes.

    Note:
        The "pointcache" and "vdbcache" product types are planned to be moved
        to a dedicated AYON ROP Cache node in a separate PR. Until that node
        exists they remain selectable on the AYON Publish ROP.
    """

    identifier = "io.ayon.creators.houdini.rop_publish"
    label = "AYON Publish"
    product_type = "rop_publish"  # TODO: Come up with better name
    product_base_type = "rop_publish"  # TODO: Come up with better name
    icon = "cubes"
    description = "Create AYON publish ROP"

    node_type = "ayon_publish"
    enable_staging_path_management = False

    def get_product_name(self, *args, **kwargs):
        """Get the product name for the selected product type.

        The AYON Publish ROP can publish any product type while the creator's
        own product base type is the generic ``rop_publish``. The name must
        be computed as if the selected product type was the creator's type,
        otherwise the 'rop_publish' product name template is used (which can
        result in names like ``rop_pointcacheMain``).
        """
        product_type = kwargs.pop("product_type", None)
        if not product_type:
            product_type = self.product_type
        if not product_type:
            return super().get_product_name(*args, **kwargs)

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                monkeypatch_attribute(self, "product_type", product_type))
            if is_func_signature_supported(
                super().get_product_name,
                *args,
                product_type=product_type,
                **kwargs,
            ):
                kwargs["product_type"] = product_type
            return super().get_product_name(*args, **kwargs)

    def get_network_categories(self):
        return [hou.ropNodeTypeCategory()]

    def get_publish_families(self):
        return ["rop_publish"]

    def imprint(self, node, values, update=False):
        # Imprint the value onto existing attributes instead
        # of trying to force create them because the HDA already
        # contains the attributes

        # Do not store product name - it's dynamically computed
        values.pop("productName", None)
        values.pop("AYON_productName", None)

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
            "active",
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

        # The HDA parm is still named 'productType' (renaming it would break
        # already saved scenes). Expose the current 'productBaseType' key that
        # the creator framework expects, falling back to the parm value.
        if not result.get("productBaseType"):
            result["productBaseType"] = result["productType"]

        # Creator attributes and publish attributes must be dict to avoid
        # bugs in publisher UI
        for key in ["creator_attributes", "publish_attributes"]:
            if not result[key]:
                result[key] = {}

        # Compute product name.
        # The name must be computed for the selected product type, not for
        # the creator's generic 'rop_publish' product base type.
        folder_path: str = result["folderPath"]
        task_name: str = result["task"]
        product_type: str = result["productType"]
        result["productName"] = self.get_product_name(
            self.create_context.get_current_project_name(),
            self.create_context.get_folder_entity(folder_path),
            self.create_context.get_task_entity(folder_path, task_name),
            variant=result["variant"],
            product_type=product_type,
        )

        return result
