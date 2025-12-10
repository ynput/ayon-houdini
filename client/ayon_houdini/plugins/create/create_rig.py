import inspect

from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef
from ayon_core.pipeline import CreatorError

import hou


class CreateRig(plugin.HoudiniCreator):
    """APEX Rig (bgeo) creator."""
    identifier = "io.ayon.creators.houdini.bgeo.rig"
    label = "Rig"
    product_type = "rig"
    product_base_type = "rig"
    icon = "wheelchair"

    description = "APEX rig exported as BGEO file"

    def get_detail_description(self):
        return inspect.cleandoc(
            """Write a BGEO output file as `rig` product type. This can be
            used to publish APEX rigs which are in essence just SOP-level
            data representing a rig structure."""
        )

    def get_publish_families(self):
        return ["rig", "bgeo", "publish.hou"]

    def create(self, product_name, instance_data, pre_create_data):
        instance = super().create(product_name, instance_data, pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        parms = {}

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

    def set_node_staging_dir(
            self, node, staging_dir, instance, pre_create_data):
        node.parm("sopoutput").set(f"{staging_dir}/$OS.$F4.{pre_create_data['bgeo_type']}")

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
