import os

import pyblish.api

from ayon_houdini.api import lib, plugin, ayon_publish

import hou


class CollectAYONPublishOutputs(plugin.HoudiniInstancePlugin):
    """Collect output representations for AYON Publish node"""

    order = pyblish.api.CollectorOrder
    label = "Collect AYON Publish ROP outputs"
    families = ["rop_publish"]

    multidot_extensions = [
        ".ass.gz",
        ".bgeo.sc",
        ".bgeo.gz",
        ".bgeo.lzma",
        ".bgeo.bz2",
    ]

    def process(self, instance):

        # Get the AYON Publish ROP node and the input ROPs we want to collect
        # as part of this instance.
        rop_node: hou.RopNode = hou.node(instance.data["instance_node"])
        if not instance.data.get("from_node", False):
            ayon_publish.set_ayon_publish_nodes_pre_render_script(
                rop_node,
                self.log,
                "",
            )
            try:
                self._rop_render(rop_node)

            finally:
                ayon_publish.set_ayon_publish_nodes_pre_render_script(
                    rop_node,
                    self.log,
                    "hou.phm().run()",
                )

        input_rops = rop_node.inputs()
        self.log.debug(f"Collecting AYON Publish ROP '{rop_node.path()}'")

        representations = instance.data.setdefault("representations", [])
        for input_rop in input_rops:
            self.log.debug(f"Processing: '{input_rop.path()}'")

            # Support fetch ROP by getting it source ROP and processing
            # that instead. This way we also support ROPs that are not inside
            # an ROPs network.
            if input_rop.type().name() == "fetch":
                fetched_rop = input_rop.parm("source").evalAsNode()
                if fetched_rop is None:
                    self.log.warning(
                        f"Skipping fetch ROP '{input_rop.path()}' as it has "
                        f"no valid source ROP set."
                    )
                    continue
                self.log.debug(f"Processing fetched ROP: {fetched_rop.path()}")
                input_rop = fetched_rop

            # TODO this does not work if first input is something like merge
            #  or switch
            try:
                filepaths = ayon_publish.get_rop_output(input_rop)
            except TypeError:
                self.log.warning(
                    f"Skipping unsupported ROP type '{input_rop.path()}' as "
                    "we can not detect its output files."
                )
                continue

            # Split extension, but allow for multi-dot extensions
            ext = lib.splitext(
                filepaths[0],
                allowed_multidot_extensions=self.multidot_extensions,
            )[-1].strip(".")

            # representation files must be single `str` if single file
            # and also must be the filename, not full path
            filenames = [os.path.basename(file) for file in filepaths]
            if len(filenames) == 1:
                filenames = filenames[0]

            representation = {
                "name": ext,
                "ext": ext,
                "files": filenames,
                "stagingDir": os.path.dirname(filepaths[0]),
            }
            self.log.debug(f"Collected representation: {representation}")
            representations.append(representation)

    def _rop_render(self, node:hou.RopNode):
        """Perform the render by node, it would raise Exception
        once there is error found.

        Args:
            node (hou.RopNode): rop node
        """
        try:
            node.render()

        except hou.OperationFailed as e:
            node.addError(f"Operation failed: {e}")
            self.log.error(f"Operation error on {node.path(): {e}}")
            raise
        except hou.PermissionError as e:
            node.addError(f"Permission error: {e}")
            self.log.error(f"Permission error on {node.path(): {e}}")
            raise
        except hou.Error as e:
            node.addError(f"Houdini error: {e}")
            self.log.error(f"Houdini error on {node.path(): {e}}")
            raise
        except Exception as e:
            node.addError(f"Unexpected error: {e}")
            self.log.error(f"Unexpected error on {node.path()}: {e}")
            raise
