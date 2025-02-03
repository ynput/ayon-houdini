# -*- coding: utf-8 -*-
import os
import hou

import pyblish.api
from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_core.pipeline.publish import (
    RepairAction,
    get_plugin_settings,
    apply_plugin_settings_automatically
)

from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectROPAction


class ResetViewSpaceAction(RepairAction):
    label = "Reset OCIO colorspace parm"
    icon = "mdi.monitor"


class ValidateReviewColorspace(plugin.HoudiniInstancePlugin,
                               OptionalPyblishPluginMixin):
    """Validate Review Colorspace parameters.

    It checks if 'OCIO Colorspace' parameter was set to valid value.
    """

    order = pyblish.api.ValidatorOrder + 0.1
    families = ["rop.opengl"]
    label = "Validate Review Colorspace"
    actions = [ResetViewSpaceAction, SelectROPAction]

    optional = True
    review_color_space = ""

    @classmethod
    def apply_settings(cls, project_settings):
        # Preserve automatic settings applying logic
        settings = get_plugin_settings(plugin=cls,
                                       project_settings=project_settings,
                                       log=cls.log,
                                       category="houdini")
        apply_plugin_settings_automatically(cls, settings, logger=cls.log)

        # workfile settings added in '0.2.13'
        color_settings = project_settings["houdini"]["imageio"].get(
            "workfile", {}
        )
        # Add review color settings
        if color_settings.get("enabled"):
            cls.review_color_space = color_settings.get("review_color_space")


    def process(self, instance):

        if not self.is_active(instance.data):
            return

        if os.getenv("OCIO") is None:
            self.log.debug(
                "Using Houdini's Default Color Management, "
                " skipping check.."
            )
            return

        rop_node = hou.node(instance.data["instance_node"])
        colorcorrect = rop_node.parm("colorcorrect").evalAsString()
        if not colorcorrect.startswith("ocio"):
            # any colorspace settings other than default requires
            # 'Color Correct' parm to be set to 'OpenColorIO'
            raise PublishValidationError(
                "'Color Correction' parm on '{}' ROP must be set to"
                " use 'OpenColorIO'".format(rop_node.path())
            )

        if colorcorrect == "ocio":
            # For both opengl and flipbook nodes.

            current_color_space = rop_node.evalParm("ociocolorspace")
            if current_color_space not in hou.Color.ocio_spaces():
                raise PublishValidationError(
                    "Invalid value: Colorspace name doesn't exist.\n"
                    "Check 'OCIO Colorspace' parameter on '{}' ROP"
                    .format(rop_node.path())
                )

            # If `ayon+settings://houdini/imageio/workfile` is enabled
            # and the Review colorspace setting is empty, then this check
            # should verify if the `current_color_space` setting equals
            # the default colorspace value.
            if self.review_color_space and \
                    self.review_color_space != current_color_space:

                raise PublishValidationError(
                    "Invalid value: Colorspace name doesn't match"
                    "the Colorspace specified in settings."
                )
            
        # TODO: Check if `ociodisplay` and `ocioview` are the same as the default display and view.
        # Should be the default value specified in settings?
        # OR Should be the current/default value specified in the hip file?
        elif colorcorrect == "ocioview":
            # For flipbook nodes only.
            pass

    @classmethod
    def repair(cls, instance):
        """Reset view colorspace.

        It is used to set colorspace on opengl node.

        It uses the colorspace value specified in the Houdini addon settings.
        If the value in the Houdini addon settings is empty,
            it will fall to the default colorspace.

        Note:
            This repair action assumes that OCIO is enabled.
            As if OCIO is disabled the whole validation is skipped
            and this repair action won't show up.
        """
        from ayon_houdini.api.lib import set_review_color_space

        # Fall to the default value if cls.review_color_space is empty.
        if not cls.review_color_space:
            # cls.review_color_space is an empty string
            #  when the imageio/workfile setting is disabled or
            #  when the Review colorspace setting is empty.
            from ayon_houdini.api.colorspace import get_default_display_view_colorspace  # noqa
            cls.review_color_space = get_default_display_view_colorspace()

        rop_node = hou.node(instance.data["instance_node"])
        set_review_color_space(rop_node,
                               cls.review_color_space,
                               cls.log)
