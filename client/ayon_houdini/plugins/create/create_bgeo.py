# -*- coding: utf-8 -*-
"""Creator plugin for creating pointcache bgeo files."""
from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatorError
import hou
from ayon_core.lib import EnumDef


class CreateBGEO(plugin.HoudiniCreator):
    """BGEO pointcache creator."""
    identifier = "io.openpype.creators.houdini.bgeo"
    label = "PointCache (Bgeo)"
    product_type = "pointcache"
    icon = "gears"

    # Default render target
    render_target = "local"

    def get_publish_families(self):
        return ["pointcache", "bgeo"]

    def create(self, product_name, instance_data, pre_create_data):

        instance_data.update({"node_type": "geometry"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super(CreateBGEO, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        file_path = "{}{}".format(
            hou.text.expandString("$HIP/pyblish/"),
            "{}.$F4.{}".format(
                product_name,
                pre_create_data.get("bgeo_type") or "bgeo.sc")
        )
        parms = {
            "sopoutput": file_path
        }

        instance_node.parm("trange").set(1)
        if self.selected_nodes:
            # if selection is on SOP level, use it
            if isinstance(self.selected_nodes[0], hou.SopNode):
                parms["soppath"] = self.selected_nodes[0].path()
            else:
                # try to find output node with the lowest index
                outputs = [
                    child for child in self.selected_nodes[0].children()
                    if child.type().name() == "output"
                ]
                if not outputs:
                    instance_node.setParms(parms)
                    raise CreatorError((
                        "Missing output node in SOP level for the selection. "
                        "Please select correct SOP path in created instance."
                    ))
                outputs.sort(key=lambda output: output.evalParm("outputidx"))
                parms["soppath"] = outputs[0].path()

        instance_node.setParms(parms)

    def get_instance_attr_defs(self):
        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
        }

        return [
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()
        bgeo_enum = [
            {
                "value": "bgeo",
                "label": "uncompressed bgeo (.bgeo)"
            },
            {
                "value": "bgeosc",
                "label": "BLOSC compressed bgeo (.bgeosc)"
            },
            {
                "value": "bgeo.sc",
                "label": "BLOSC compressed bgeo (.bgeo.sc)"
            },
            {
                "value": "bgeo.gz",
                "label": "GZ compressed bgeo (.bgeo.gz)"
            },
            {
                "value": "bgeo.lzma",
                "label": "LZMA compressed bgeo (.bgeo.lzma)"
            },
            {
                "value": "bgeo.bz2",
                "label": "BZip2 compressed bgeo (.bgeo.bz2)"
            }
        ]

        return attrs + [
            EnumDef(
                "bgeo_type",
                bgeo_enum,
                default="bgeo.sc",
                label="BGEO Options"
            ),
        ] + self.get_instance_attr_defs()

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.sopNodeTypeCategory()
        ]
