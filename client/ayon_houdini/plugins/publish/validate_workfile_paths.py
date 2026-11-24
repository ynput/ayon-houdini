# -*- coding: utf-8 -*-
from __future__ import annotations

import re

import hou

import pyblish.api
from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_core.pipeline.publish import RepairAction

from ayon_houdini.api import plugin
from ayon_houdini.api.lib import expand_houdini_vars


def find_used_vars(value: str) -> set[str]:
    """Return used vars in value as whole variable names.

    Matches `${HIP}` the same as `$HIP`.

    Returns:
        set[str]: Set of used variable names (without `$` prefix)

    Examples:
        >>> find_used_vars("$HIP")
        {"HIP"}

        >>> find_used_vars("${HIP}")
        {"HIP"}

        >>> find_used_vars("$JOB/some/path/${OS}.${HIPNAME:r}.exr")
        {"JOB", "OS", "HIPNAME"}

    """
    names = re.findall(r"\$\{?([\w:]+)\}?", value)
    names = {name.split(":")[0] for name in names}  # strip modifiers `HIPNAME:r`  # noqa: E501
    return names

class ValidateWorkfilePaths(
        plugin.HoudiniInstancePlugin, OptionalPyblishPluginMixin):
    """Validate workfile paths so they are absolute."""

    order = pyblish.api.ValidatorOrder
    families = ["workfile"]
    label = "Validate Workfile Paths"
    actions = [RepairAction]
    optional = True

    node_types = ["file", "alembic"]
    prohibited_vars = ["$HIP", "$JOB"]

    @classmethod
    def find_prohibited_vars(cls, value: str) -> set[str]:
        """Return prohibited vars used in value as whole variable names."""
        used_vars = find_used_vars(value)
        prohibited = {var.removeprefix("$") for var in cls.prohibited_vars}
        return used_vars & prohibited

    def process(self, instance):
        if not self.is_active(instance.data):
            return
        invalid = self.get_invalid()
        self.log.debug(
            "Checking node types: {}".format(", ".join(self.node_types)))
        self.log.debug(
            "Searching prohibited vars: {}".format(
                ", ".join(self.prohibited_vars)
            )
        )

        if invalid:
            all_container_vars = set()
            for param in invalid:
                value = param.unexpandedString()
                contained_vars = self.find_prohibited_vars(value)
                all_container_vars.update(contained_vars)

                self.log.error(
                    "Parm {} contains prohibited vars {}: {}".format(
                        param.path(),
                        ", ".join(contained_vars),
                        value)
                )

            message = (
                "Prohibited vars {} found in parameter values".format(
                    ", ".join(all_container_vars)
                )
            )
            raise PublishValidationError(message, title=self.label)

    @classmethod
    def get_invalid(cls) -> list[hou.Parm]:
        """Return invalid parameters."""
        invalid = []
        for param, _ in hou.fileReferences():
            # it might return None for some reason
            if not param:
                continue
            # skip nodes we are not interested in
            if param.node().type().name() not in cls.node_types:
                continue

            if param.keyframes():
                # Calling `.unexpandedString()` below fails if param has
                # keyframes - so for now we will skip those params. These are
                # e.g. present in `filecache` nodes.
                continue

            value = param.unexpandedString()
            if cls.find_prohibited_vars(value):
                invalid.append(param)

        return invalid

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid()
        for param in invalid:
            cls.log.info(f"Processing: '{param.path()}'.")
            value = param.unexpandedString()
            expanded = expand_houdini_vars(
                text=value,
                names=cls.prohibited_vars,
                context=param,
            )
            cls.log.info(f"Replacing '{value}' for '{expanded}'.")

            param.set(expanded)
