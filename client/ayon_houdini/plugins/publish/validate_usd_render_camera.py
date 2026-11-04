# -*- coding: utf-8 -*-
import inspect
import hou
import pxr
from pxr import UsdRender
import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError

from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


class ValidateUSDRenderCamera(plugin.HoudiniInstancePlugin):
    """Validate USD Render Settings refer to a valid render camera.

    The render camera is defined in priority by this order:
        1. ROP Node Override Camera Parm (if set)
        2. Render Product Camera (if set - this may differ PER render product!)
        3. Render Settings Camera (if set)

    If None of these are set *or* a currently set entry resolves to an invalid
    camera prim path then we'll report it as an error.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render Camera"
    actions = [SelectROPAction]

    def process(self, instance):

        rop_node = hou.node(instance.data["instance_node"])
        lop_node = instance.data.get("output_node")
        if not lop_node:
            # No valid output node was set. We ignore it since it will
            # be validated by another plug-in.
            return

        stage = instance.data["stage"]
        render_settings = instance.data["rendersettings"]
        if not render_settings:
            # Without render settings we basically have no defined
            self.log.error("No render settings found for %s.", rop_node.path())
            return

        render_settings_camera = self._get_camera(render_settings)
        rop_camera = rop_node.evalParm("override_camera")

        invalid = False
        camera_paths = set()
        for render_product in self.iter_render_products(render_settings,
                                                        stage):
            render_product_camera = self._get_camera(render_product)

            # Get first camera path as per order in in this plug-in docstring
            camera_path = next(
                (cam_path for cam_path in [rop_camera,
                                           render_product_camera,
                                           render_settings_camera]
                 if cam_path),
                None
            )
            if not camera_path:
                self.log.error(
                    "No render camera defined for render product: '%s'",
                    render_product.GetPath()
                )
                invalid = True
                continue

            camera_paths.add(camera_path)

        # For the camera paths used across the render products detect
        # whether the path is a valid camera in the stage
        for camera_path in sorted(camera_paths):
            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim or not camera_prim.IsValid():
                self.log.error(
                    "Render camera path '%s' does not exist in stage.",
                    camera_path
                )
                invalid = True
                continue

            if not camera_prim.IsA(pxr.UsdGeom.Camera):
                self.log.error(
                    "Render camera path '%s' is not a camera.",
                    camera_path
                )
                invalid = True

        if invalid:
            raise PublishValidationError(
                f"No render camera found for {instance.name}.",
                title="Invalid Render Camera",
                description=self.get_description()
            )

    def iter_render_products(self, render_settings, stage):
        for product_path in render_settings.GetProductsRel().GetTargets():
            prim = stage.GetPrimAtPath(product_path)
            if prim.IsA(UsdRender.Product):
                yield UsdRender.Product(prim)

    def _get_camera(self, settings: UsdRender.SettingsBase):
        """Return primary camera target from RenderSettings or RenderProduct"""
        camera_targets = settings.GetCameraRel().GetForwardedTargets()
        if camera_targets:
            return camera_targets[0]

    def get_description(self):
        return inspect.cleandoc(
            """### Missing render camera

            No valid render camera was set for the USD Render Settings.

            The configured render camera path must be a valid camera in the
            stage. Make sure it refers to an existing path and that it is
            a camera.

            """
        )
