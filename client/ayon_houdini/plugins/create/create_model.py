# -*- coding: utf-8 -*-
"""Creator plugin for creating Model product type.

Note:
    Currently, This creator plugin is the same as 'create_pointcache.py'
    But renaming the product type to 'model'.

    It's purpose to support
    Maya (load/publish model from maya to/from houdini).

    It's considered to support multiple representations in the future.
"""

from ayon_houdini.api import plugin
from ayon_core.lib import EnumDef

import hou


class CreateModel(plugin.HoudiniCreator):
    """Create Model"""
    identifier = "io.openpype.creators.houdini.model"
    label = "Model"
    product_type = "model"
    icon = "cube"

    # Default render target
    render_target = "local"

    def get_publish_families(self):
        return ["model", "abc"]

    def create(self, product_name, instance_data, pre_create_data):
        instance_data.update({"node_type": "alembic"})
        creator_attributes = instance_data.setdefault(
            "creator_attributes", dict())
        creator_attributes["render_target"] = pre_create_data["render_target"]

        instance = super(CreateModel, self).create(
            product_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))
        parms = {
            "use_sop_path": True,
            "build_from_path": True,
            "path_attrib": "path",
            "prim_to_detail_pattern": "cbId",
            "format": 2,
            "facesets": 0,
            "filename": hou.text.expandString(
                "$HIP/pyblish/{}.abc".format(product_name))
        }

        if self.selected_nodes:
            selected_node = self.selected_nodes[0]

            # Although Houdini allows ObjNode path on `sop_path` for the
            # the ROP node we prefer it set to the SopNode path explicitly

            # Allow sop level paths (e.g. /obj/geo1/box1)
            if isinstance(selected_node, hou.SopNode):
                parms["sop_path"] = selected_node.path()
                self.log.debug(
                   "Valid SopNode selection, 'SOP Path' in ROP"
                   " will be set to '%s'."
                   % selected_node.path()
                )

            # Allow object level paths to Geometry nodes (e.g. /obj/geo1)
            #   but do not allow other object level nodes types
            #   like cameras, etc.
            elif isinstance(selected_node, hou.ObjNode) and \
                    selected_node.type().name() in ["geo"]:

                # get the output node with the minimum
                # 'outputidx' or the node with display flag
                sop_path = self.get_obj_output(selected_node)

                if sop_path:
                    parms["sop_path"] = sop_path.path()
                    self.log.debug(
                        "Valid ObjNode selection, 'SOP Path' in ROP"
                        " will be set to the child path '%s'."
                        % sop_path.path()
                    )

            if not parms.get("sop_path", None):
                self.log.debug(
                    "Selection isn't valid. 'SOP Path' in ROP will be empty."
                )
        else:
            self.log.debug(
                "No Selection. 'SOP Path' in ROP will be empty."
            )

        instance_node.setParms(parms)
        instance_node.parm("trange").set(1)

        # Explicitly set f1 and f2 to frame start.
        # Which forces the rop node to export one frame.
        instance_node.parmTuple('f').deleteAllKeyframes()
        fstart = int(hou.hscriptExpression("$FSTART"))
        instance_node.parmTuple('f').set((fstart, fstart, 1))

        # Lock any parameters in this list
        to_lock = ["prim_to_detail_pattern"]
        self.lock_parameters(instance_node, to_lock)

    def get_network_categories(self):
        return [
            hou.ropNodeTypeCategory(),
            hou.sopNodeTypeCategory()
        ]

    def get_obj_output(self, obj_node):
        """Find output node with the smallest 'outputidx'."""

        outputs = obj_node.subnetOutputs()

        # if obj_node is empty
        if not outputs:
            return

        # if obj_node has one output child whether its
        # sop output node or a node with the render flag
        elif len(outputs) == 1:
            return outputs[0]

        # if there are more than one, then it have multiple output nodes
        # return the one with the minimum 'outputidx'
        else:
            return min(outputs,
                       key=lambda node: node.evalParm('outputidx'))

    def get_instance_attr_defs(self):
        render_target_items = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
            "farm_no_render": "Use existing frames (farm)"
        }

        return [
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target)
        ]

    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()
        # Use same attributes as for instance attributes
        return attrs + self.get_instance_attr_defs()
