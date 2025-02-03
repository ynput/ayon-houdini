# -*- coding: utf-8 -*-
"""Creator plugin for creating composite sequences."""
from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatorError

import hou


class CreateCompositeSequence(plugin.HoudiniCreator):
    """Composite ROP to Image Sequence"""

    identifier = "io.openpype.creators.houdini.imagesequence"
    label = "Composite (Image Sequence)"
    product_type = "imagesequence"
    icon = "gears"

    ext = ".exr"

    def create(self, product_name, instance_data, pre_create_data):
        import hou  # noqa

        instance_data.update({"node_type": "comp"})

        instance = super(CreateCompositeSequence, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))
        parms = {
            "trange": 1,
        }

        if self.selected_nodes:
            if len(self.selected_nodes) > 1:
                raise CreatorError("More than one item selected.")
            path = self.selected_nodes[0].path()
            parms["coppath"] = path

        instance_node.setParms(parms)

        # Manually set f1 & f2 to $FSTART and $FEND respectively
        # to match other Houdini nodes default.
        instance_node.parm("f1").setExpression("$FSTART")
        instance_node.parm("f2").setExpression("$FEND")

        # Lock any parameters in this list
        to_lock = ["prim_to_detail_pattern"]
        self.lock_parameters(instance_node, to_lock)

    def set_node_staging_dir(self, node, staging_dir, instance, pre_create_data):
        node.parm("copoutput").set(f"{staging_dir}/$OS.$F4{self.ext}")

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.cop2NodeTypeCategory()
        ]
