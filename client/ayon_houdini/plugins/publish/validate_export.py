# -*- coding: utf-8 -*-
import hou

import pyblish.api

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction

from ayon_houdini.api.action import SelectInvalidAction
from ayon_houdini.api import plugin


class FixParameterAction(RepairAction):
    label = "Fix Export Parameter"


class ValidateExportParameterValue(plugin.HoudiniInstancePlugin):
    """Validate Export Parameter Value on render rop nodes.

    This is associated to render nodes where we can
    split export and render DL jobs.

    Note: 
        This validator mostly fails when users change render target
        as changing render target doesn't change the export parameter
        on the rop node accordingly.
        More Info: https://github.com/ynput/ayon-houdini/issues/16
    """

    order = pyblish.api.ValidatorOrder
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender"]
    label = "Validate Export Toggle"
    actions = [FixParameterAction, SelectInvalidAction]

    export_info = {
        "arnold": {
            "export_parameter": "ar_ass_export_enable",
            "mode": {
                "export": 1,
                "no_export": 0
            }
        },
        "ifd": {
            "export_parameter": "soho_outputmode",
            "mode": {
                "export": 1,
                "no_export": 0
            }
        },
        "Redshift_ROP": {
            "export_parameter": "RS_archive_enable",
            "mode": {
                "export": 1,
                "no_export": 0
            }
        },
        "vray_renderer": {
            "export_parameter": "render_export_mode",
            "mode": {
                "export": "2",
                "no_export": "1"
            }
        },
        "usdrender": {
            "export_parameter": "runcommand",
            "mode": {
                "export": 0,
                "no_export": 1
            }
        },
    }

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            rop_node = invalid[0]
            node_type = rop_node.type().name()
            raise PublishValidationError(
                f"ROP node {rop_node.path()} has incorrect value for export "
                f"parm: {self.export_info[node_type]['export_parameter']}",
                title=self.label
            )

    @classmethod
    def get_invalid(cls, instance):
        # Check if export parameter value on rop node has the expected
        # value that aligns with the current render target.

        rop_node = hou.node(instance.data["instance_node"])
        node_type = rop_node.type().name()
        export_parameter = cls.export_info[node_type]["export_parameter"]
        export_mode = \
            "export" if instance.data["splitRender"] else "no_export"
        export_value = cls.export_info[node_type]["mode"][export_mode]
        if rop_node.evalParm(export_parameter) != export_value:
            return [rop_node]

    @classmethod
    def repair(cls, instance):

        if not cls.get_invalid(instance):
            # Already fixed
            return

        # Align split parameter value on rop node to the render target.
        rop_node = hou.node(instance.data["instance_node"])
        node_type = rop_node.type().name()
        export_parameter = cls.export_info[node_type]["export_parameter"]
        export_mode = \
            "export" if instance.data["splitRender"] else "no_export"
        export_value = cls.export_info[node_type]["mode"][export_mode]

        rop_node.setParms({export_parameter: export_value})