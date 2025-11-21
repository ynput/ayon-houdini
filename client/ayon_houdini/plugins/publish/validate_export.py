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

    # Per ROP node type, define the export parameter and expected values
    # for export and no export modes. The first entry is for export mode,
    # the second for no export mode.
    export_info = {
        "arnold": {
            "ar_ass_export_enable": [1, 0]
        },
        "ifd": {
            "soho_outputmode": [1, 0]
        },
        "Redshift_ROP": {
            "RS_archive_enable": [1, 0]
        },
        "vray_renderer": {
            "render_export_mode": ["2", "1"]
        },
        "usdrender": {
            "runcommand": [0, 1]
        },
    }

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            rop_node = invalid[0]
            node_type = rop_node.type().name()
            required_parms = ", ".join(self.export_info[node_type])
            raise PublishValidationError(
                f"ROP node {rop_node.path()} has incorrect value for "
                f"parms: {required_parms}",
                title=self.label
            )

    @classmethod
    def get_invalid(cls, instance):
        # Check if export parameter value on rop node has the expected
        # value that aligns with the current render target.
        rop_node = hou.node(instance.data["instance_node"])
        node_type = rop_node.type().name()
        for parm_name, (on, off) in cls.export_info[node_type].items():
            required_value = (
                on if instance.data["splitRender"] else off
            )
            parm = rop_node.parm(parm_name)
            current_value = parm.eval()
            if current_value != required_value:
                cls.log.debug(
                    f"ROP node {parm.path()} has invalid value {current_value}"
                    f" but should be {required_value}"
                )
                return [rop_node]

    @classmethod
    def repair(cls, instance):
        if not cls.get_invalid(instance):
            # Already fixed
            return

        rop_node = hou.node(instance.data["instance_node"])
        node_type = rop_node.type().name()

        # Set required values
        parm_values = {}
        for parm_name, (on, off) in cls.export_info[node_type].items():
            required_value = (
                on if instance.data["splitRender"] else off
            )
            parm_values[parm_name] = required_value
        rop_node.setParms(parm_values)
