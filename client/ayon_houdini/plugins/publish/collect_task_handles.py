# -*- coding: utf-8 -*-
"""Collector plugin for frames data on ROP instances."""
from __future__ import annotations

import pyblish.api
from ayon_core.lib import BoolDef
from ayon_core.pipeline import AYONPyblishPluginMixin
from ayon_houdini.api import plugin


class CollectAssetHandles(plugin.HoudiniInstancePlugin,
                          AYONPyblishPluginMixin):
    """Apply instance's task entity handles.

    If instance does not have:
        - frameStart
        - frameEnd
        - handleStart
        - handleEnd
    But it does have:
        - frameStartHandle
        - frameEndHandle

    Then we will retrieve the task's handles to compute
    the exclusive frame range and actual handle ranges.
    """
    # TODO: This also validates against model products, even though those
    #  should export a single frame regardless so maybe it's redundantly
    #  validating?

    # This specific order value is used so that
    # this plugin runs after CollectAnatomyInstanceData
    order = pyblish.api.CollectorOrder + 0.499

    label = "Collect Task Handles"
    use_asset_handles = True

    ignore_product_types: set[str] = {"rig"}

    def process(self, instance):

        # Do no check asset handles for products that are essentially not
        # intended to be time-based
        if instance.data.get("productType") in self.ignore_product_types:
            return

        # Only process instances without already existing handles data
        # but that do have frameStartHandle and frameEndHandle defined
        # like the data collected from CollectRopFrameRange
        if "frameStartHandle" not in instance.data:
            return
        if "frameEndHandle" not in instance.data:
            return

        has_existing_data = {
            "handleStart",
            "handleEnd",
            "frameStart",
            "frameEnd"
        }.issubset(instance.data)
        if has_existing_data:
            return

        attr_values = self.get_attr_values_from_data(instance.data)
        if attr_values.get("use_handles", self.use_asset_handles):
            # Get from task (if task is set), otherwise from folder
            entity = instance.data.get("taskEntity",
                                       instance.data["folderEntity"])
            handle_start = entity["attrib"].get("handleStart", 0)
            handle_end = entity["attrib"].get("handleEnd", 0)
        else:
            handle_start = 0
            handle_end = 0

        frame_start = instance.data["frameStartHandle"] + handle_start
        frame_end = instance.data["frameEndHandle"] - handle_end

        instance.data.update({
            "handleStart": handle_start,
            "handleEnd": handle_end,
            "frameStart": frame_start,
            "frameEnd": frame_end
        })

        # Log debug message about the collected frame range
        if attr_values.get("use_handles", self.use_asset_handles):
            self.log.debug(
                "Full Frame range with Handles "
                "[{frame_start_handle} - {frame_end_handle}]"
                .format(
                    frame_start_handle=instance.data["frameStartHandle"],
                    frame_end_handle=instance.data["frameEndHandle"]
                )
            )
        else:
            self.log.debug(
                "Use handles is deactivated for this instance, "
                "start and end handles are set to 0."
            )

        # Log collected frame range to the user
        message = "Frame range [{frame_start} - {frame_end}]".format(
            frame_start=frame_start,
            frame_end=frame_end
        )
        if handle_start or handle_end:
            message += " with handles [{handle_start}]-[{handle_end}]".format(
                handle_start=handle_start,
                handle_end=handle_end
            )
        self.log.info(message)

        if instance.data.get("byFrameStep", 1.0) != 1.0:
            self.log.info(
                "Frame steps {}".format(instance.data["byFrameStep"]))

        # Add frame range to label if the instance has a frame range.
        label = instance.data.get("label", instance.data["name"])
        instance.data["label"] = (
            "{label} [{frame_start_handle} - {frame_end_handle}]"
            .format(
                label=label,
                frame_start_handle=instance.data["frameStartHandle"],
                frame_end_handle=instance.data["frameEndHandle"]
            )
        )

    @classmethod
    def get_attr_defs_for_instance(cls, create_context, instance):
        if not cls.instance_matches_plugin_families(instance):
            return []

        if instance.data.get("productType") in cls.ignore_product_types:
            return []

        return [
            BoolDef("use_handles",
                    tooltip="Disable this if you want the publisher to"
                    " ignore start and end handles specified in the"
                    " task attributes for this publish instance",
                    default=cls.use_asset_handles,
                    label="Use task handles")
        ]
