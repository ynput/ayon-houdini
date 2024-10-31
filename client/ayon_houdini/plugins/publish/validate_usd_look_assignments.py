# -*- coding: utf-8 -*-
import inspect
from typing import Iterable, Optional, List

from pxr import Sdf, Usd, UsdShade, UsdGeom

import pyblish.api

from ayon_core.pipeline.publish import (
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_houdini.api.action import SelectROPAction
from ayon_houdini.api import plugin


def has_material(prim: Usd.Prim,
                 include_subsets: bool = True,
                 purposes: Optional[Iterable[str]] = None) -> bool:
    """Return whether primitive has any material binding."""
    if purposes is None:
        purposes = [UsdShade.Tokens.allPurpose]

    search_from = [prim]
    if include_subsets:
        subsets = UsdShade.MaterialBindingAPI(prim).GetMaterialBindSubsets()
        for subset in subsets:
            search_from.append(subset.GetPrim())

    for purpose in purposes:
        bounds = UsdShade.MaterialBindingAPI.ComputeBoundMaterials(search_from,
                                                                   purpose)
        for (material, relationship) in zip(*bounds):
            material_prim = material.GetPrim()
            if material_prim.IsValid():
                # Has a material binding
                return True

    return False


class ValidateUsdLookAssignments(plugin.HoudiniInstancePlugin,
                                 OptionalPyblishPluginMixin):
    """Validate all geometry prims have a material binding.

    Note: This does not necessarily validate the material binding is authored
        by the current layers if the input already had material bindings.

    """

    order = pyblish.api.ValidatorOrder
    families = ["look"]
    hosts = ["houdini"]
    label = "Validate All Geometry Has Material Assignment"
    actions = [SelectROPAction]
    optional = True

    # The USD documentation mentions that it's okay to have custom material
    # purposes but the USD standard only supports 2 (technically 3, since
    # allPurpose is empty)
    allowed_material_purposes = (
        UsdShade.Tokens.full,
        UsdShade.Tokens.preview,
        UsdShade.Tokens.allPurpose,
    )

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # Get Usd.Stage from "Collect ROP Sdf Layers and USD Stage" plug-in
        stage = instance.data.get("stage")
        if not stage:
            self.log.debug("No USD stage found.")
            return
        stage: Usd.Stage

        # We iterate the composed stage for code simplicity; however this
        # means that it does not validate across e.g. multiple model variants
        # but only checks against the current composed stage. Likely this is
        # also what you actually want to validate, because your look might not
        # apply to *all* model variants.
        invalid: List[Sdf.Path] = []
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Gprim):
                continue

            if not has_material(prim, purposes=self.allowed_material_purposes):
                invalid.append(prim.GetPath())

        for path in sorted(invalid):
            self.log.warning("No material binding on: %s", path.pathString)

        if invalid:
            raise PublishValidationError(
                "Found geometry without material bindings.",
                title="No assigned materials",
                description=self.get_description()
            )

    @staticmethod
    def get_description():
        return inspect.cleandoc(
            """### Geometry has no material assignments.

            A look publish should usually define a material assignment for all
            geometry of a model. As such, this validates whether all geometry
            currently has at least one material binding applied.

            """
        )
