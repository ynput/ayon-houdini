import inspect

import pyblish.api
import hou
from pxr import Usd, UsdRender

from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
)
from ayon_core.pipeline.publish import get_errored_instances_from_context

from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api.usd import (
    get_usd_rop_loppath,
    get_usd_render_rop_rendersettings
)


class JumpToEditorNodeAction(pyblish.api.Action):
    """Select the editor nodes related to the USD attributes.

    If a "Render Settings" node in the current Houdini scene defined the
    Render Settings primitive or changed the resolution attribute this would
    select the LOP node that set that attribute.

    It does so by using the `HoudiniPrimEditorNodes` custom data on the USD
    object that Houdini stores when editing a USD attribute.
    """
    label = "Jump to Editor Node"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "search"  # Icon from Awesome Icon

    get_invalid_objects_fn = "get_invalid_resolution"

    def process(self, context, plugin):
        errored_instances = get_errored_instances_from_context(context,
                                                               plugin=plugin)

        # Get the invalid nodes for the plug-ins
        self.log.info("Finding invalid nodes..")
        objects: "list[Usd.Object]" = list()
        for instance in errored_instances:

            get_invalid = getattr(plugin, self.get_invalid_objects_fn)
            invalid_objects = get_invalid(instance)
            if invalid_objects:
                if isinstance(invalid_objects, (list, tuple)):
                    objects.extend(invalid_objects)
                else:
                    self.log.warning("Plug-in returned to be invalid, "
                                     "but has no selectable nodes.")

        if not objects:
            self.log.info("No invalid objects found.")

        nodes: "list[hou.Node]" = []
        for obj in objects:
            lop_editor_nodes = self.get_lop_editor_node(obj)
            if lop_editor_nodes:
                # Get the last entry because it is the last node in the graph
                # that edited attribute or prim. For that node find the first
                # editable node so that we do not select inside e.g. a locked
                # HDA.
                editable_node = self.get_editable_node(lop_editor_nodes[-1])
                nodes.append(editable_node)

        hou.clearAllSelected()
        if nodes:
            self.log.info("Selecting invalid nodes: {}".format(
                ", ".join(node.path() for node in nodes)
            ))
            for node in nodes:
                node.setSelected(True)
                node.setCurrent(True)
        else:
            self.log.info("No invalid nodes found.")

    def get_lop_editor_node(self, obj: Usd.Object):
        """Return Houdini LOP Editor node from a USD object.

        If the object is a USD attribute but has no editor nodes, it will
        try to find the editor nodes from the parent prim.

        Arguments:
            obj (Usd.Object): USD object

        Returns:
            list[hou.Node]: Houdini LOP Editor nodes, if set in the custom
                data of the object.

        """
        key = "HoudiniPrimEditorNodes"
        editor_nodes = obj.GetCustomDataByKey(key)
        if not editor_nodes and isinstance(obj, Usd.Attribute):
            prim = obj.GetPrim()
            editor_nodes = prim.GetCustomDataByKey(key)

        if not editor_nodes:
            return []
        return [hou.nodeBySessionId(node) for node in editor_nodes]

    def get_editable_node(self, node: hou.Node):
        """Return the node or nearest parent that is editable.

        If the node is inside a locked HDA and it's not editable, then go up
        to the first parent that is editable.

        Returns:
            hou.Node: The node itself or the first parent that is editable.
        """
        while node.isInsideLockedHDA():
            # Allow editable node inside HDA
            if node.isEditableInsideLockedHDA():
                return node
            node = node.parent()
        return node


class ValidateRenderResolution(plugin.HoudiniInstancePlugin,
                               OptionalPyblishPluginMixin):
    """Validate the render resolution setting aligned with DB"""

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    label = "Validate Render Resolution"
    actions = [SelectROPAction, JumpToEditorNodeAction]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid_resolution(instance)
        if invalid:
            raise PublishValidationError(
                "Render resolution does not match the entity's resolution for "
                "the current context. See log for details.",
                description=self.get_description()
            )

    @classmethod
    def get_invalid_resolution(cls, instance):
        # Get render resolution and pixel aspect ratio from USD stage
        rop_node = hou.node(instance.data["instance_node"])
        lop_node: hou.LopNode = get_usd_rop_loppath(rop_node)
        if not lop_node:
            cls.log.debug(
                f"No LOP node found for ROP node: {rop_node.path()}")
            return

        stage: Usd.Stage = lop_node.stage()
        render_settings: UsdRender.Settings = (
            get_usd_render_rop_rendersettings(rop_node, stage, logger=cls.log))
        if not render_settings:
            cls.log.debug(
                f"No render settings found for LOP node: {lop_node.path()}")
            return

        invalid = []

        # Each render product can have different resolution set if explicitly
        # overridden. If not set, it will use the resolution from the render
        # settings.
        sample_time = Usd.TimeCode.EarliestTime()

        # Get all resolution and pixel aspect attributes to validate
        resolution_attributes = [render_settings.GetResolutionAttr()]
        pixel_aspect_attributes = [render_settings.GetPixelAspectRatioAttr()]
        for product in cls.iter_render_products(render_settings, stage):
            resolution_attr = product.GetResolutionAttr()
            if resolution_attr.HasAuthoredValue():
                resolution_attributes.append(resolution_attr)

            pixel_aspect_attr = product.GetPixelAspectRatioAttr()
            if pixel_aspect_attr.HasAuthoredValue():
                pixel_aspect_attributes.append(pixel_aspect_attr)

        # Validate resolution and pixel aspect ratio
        width, height, pixel_aspect = cls.get_expected_resolution(instance)
        for resolution_attr in resolution_attributes:
            current_width, current_height = resolution_attr.Get(sample_time)
            if current_width != width or current_height != height:
                cls.log.error(
                    f"{resolution_attr.GetPath()}: "
                    f"{current_width}x{current_height} "
                    f"does not match context resolution {width}x{height}"
                )
                invalid.append(resolution_attr)

        for pixel_aspect_attr in pixel_aspect_attributes:
            current_pixel_aspect = pixel_aspect_attr.Get(sample_time)
            if current_pixel_aspect != pixel_aspect:
                cls.log.error(
                    f"{pixel_aspect_attr.GetPath()}: "
                    f"{current_pixel_aspect} does not "
                    f"match context pixel aspect {pixel_aspect}")
                invalid.append(pixel_aspect_attr)

        return invalid

    @classmethod
    def get_expected_resolution(cls, instance):
        """Return the expected resolution and pixel aspect ratio for the 
        instance based on the task entity or folder entity."""

        entity = instance.data.get("taskEntity")
        if not entity:
            entity = instance.data["folderEntity"]

        attributes = entity["attrib"]
        width = attributes["resolutionWidth"]
        height = attributes["resolutionHeight"]
        pixel_aspect = attributes["pixelAspect"]
        return int(width), int(height), float(pixel_aspect)

    @classmethod
    def iter_render_products(cls, render_settings, stage):
        """Iterate over all render products in the USD render settings"""
        for product_path in render_settings.GetProductsRel().GetTargets():
            prim = stage.GetPrimAtPath(product_path)
            if not prim.IsValid():
                cls.log.debug(
                    f"Render product path is not a valid prim: {product_path}")
                return

            if prim.IsA(UsdRender.Product):
                yield UsdRender.Product(prim)
                
    @staticmethod
    def get_description():
        return inspect.cleandoc("""
            ### Render Resolution does not match context
            
            The render resolution or pixel aspect ratio does not match the 
            resolution configured in the project database. Please ensure the 
            render resolution is set correctly.
            
            #### USD Render Settings
            
            In most cases the render resolution is defined via the Render 
            Settings prim in USD, however each Render Product is capable
            of authoring its own override. The logs will report the exact 
            attribute path for the mismatching resolution or aspect ratio.
        """)
