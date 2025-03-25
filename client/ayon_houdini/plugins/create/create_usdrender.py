# -*- coding: utf-8 -*-
"""Creator plugin for creating USD renders."""
from ayon_houdini.api import plugin
from ayon_core.lib import BoolDef, EnumDef

import hou


def get_usd_rop_renderers():
    """Return all available renderers supported by USD Render ROP.
    Note that the USD Render ROP does not include all Hydra renderers, because
    it excludes the GL ones like Houdini GL and Storm. USD Render ROP only
    lists the renderers that have `aovsupport` enabled. Also see:
        https://www.sidefx.com/docs/houdini/nodes/out/usdrender.html#list
    Returns:
        dict[str, str]: Plug-in name to display name mapping.
    """
    return {
        info["name"]: info["displayname"] for info
        in hou.lop.availableRendererInfo() if info.get('aovsupport')
    }


class CreateUSDRender(plugin.HoudiniCreator):
    """USD Render ROP in /stage"""
    identifier = "io.openpype.creators.houdini.usdrender"
    label = "USD Render"
    product_type = "usdrender"
    icon = "magic"
    description = "Create USD Render"

    default_renderer = "Karma CPU"
    # Default render target
    render_target = "farm_split"

    def create(self, product_name, instance_data, pre_create_data):

        # Transfer settings from pre create to instance
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())

        for key in ["render_target", "review"]:
            if key in pre_create_data:
                creator_attributes[key] = pre_create_data[key]

        # TODO: Support creation in /stage if wanted by user
        # pre_create_data["parent"] = "/stage"

        instance_data.update({"node_type": "usdrender"})

        # Override default value for the Export Chunk Size because if the
        # a single USD file is written as opposed to per frame we want to
        # ensure only one machine picks up that sequence
        # TODO: Probably better to change the default somehow for just this
        #    Creator on the HoudiniSubmitDeadline plug-in, if possible?
        (
            instance_data
            .setdefault("publish_attributes", {})
            .setdefault("HoudiniSubmitDeadlineUsdRender", {})["export_chunk"]
        ) = 1000

        instance = super(CreateUSDRender, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        parms = {
            # Render frame range
            "trange": 1
        }
        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        if pre_create_data.get("render_target") == "farm_split":
            # Do not trigger the husk render, only trigger the USD export
            parms["runcommand"] = False
            # By default, the render ROP writes out the render file to a
            # temporary directory. But if we want to render the USD file on
            # the farm we instead want it in the project available
            # to all machines. So we ensure all USD files are written to a
            # folder to our choice. The
            # `__render__.usd` (default name, defined by `lopoutput` parm)
            # in that folder will then be the file to render.
            parms["savetodirectory_directory"] = "$HIP/render/usd/$HIPNAME/$OS"
            parms["lopoutput"] = "__render__.usd"
            parms["allframesatonce"] = True

        # By default strip any Houdini custom data from the output file
        # since the renderer doesn't care about it
        parms["clearhoudinicustomdata"] = True

        # Use the first selected LOP node if "Use Selection" is enabled
        # and the user had any nodes selected
        if self.selected_nodes:
            for node in self.selected_nodes:
                if node.type().category() == hou.lopNodeTypeCategory():
                    parms["loppath"] = node.path()
                    break

        # Set default renderer if defined in settings
        if pre_create_data.get("renderer"):
            parms["renderer"] = pre_create_data.get("renderer")

        instance_node.setParms(parms)

        # Lock some AYON attributes
        to_lock = ["productType", "id"]
        self.lock_parameters(instance_node, to_lock)

    def get_instance_attr_defs(self):
        """get instance attribute definitions.
        Attributes defined in this method are exposed in
            publish tab in the publisher UI.
        """

        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
            "farm_split": "Farm Rendering - Split export & render jobs",
        }

        return [
            BoolDef("review",
                    label="Review",
                    tooltip="Mark as reviewable",
                    default=True),
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):

        # Retrieve available renderers and convert default renderer to
        # plug-in name if settings provided the display name
        renderer_plugin_to_display_name = get_usd_rop_renderers()
        default_renderer = self.default_renderer or None
        if (
            default_renderer
            and default_renderer not in renderer_plugin_to_display_name
        ):
            # Map default renderer display name to plugin name
            for name, display_name in renderer_plugin_to_display_name.items():
                if default_renderer == display_name:
                    default_renderer = name
                    break
            else:
                # Default renderer not found in available renderers
                default_renderer = None

        attrs = super(CreateUSDRender, self).get_pre_create_attr_defs()
        attrs += [
            EnumDef("renderer",
                    label="Renderer",
                    default=default_renderer,
                    items=renderer_plugin_to_display_name),
        ]

        return attrs + self.get_instance_attr_defs()
