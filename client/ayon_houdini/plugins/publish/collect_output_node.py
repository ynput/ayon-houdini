import pyblish.api
from ayon_core.pipeline.publish import KnownPublishError
from ayon_houdini.api import plugin


class CollectOutputSOPPath(plugin.HoudiniInstancePlugin):
    """Collect the out node's SOP/COP Path value."""

    order = pyblish.api.CollectorOrder - 0.45
    families = [
        "pointcache",
        "camera",
        "vdbcache",
        "imagesequence",
        "redshiftproxy",
        "staticMesh",
        "model",
        "usdrender",
        "usdrop"
    ]

    label = "Collect Output Node Path"

    def process(self, instance):

        import hou

        node = hou.node(instance.data["instance_node"])

        # Get sop path
        node_type = node.type().name()
        if node_type in {"geometry", "PRT_ROPDriver"}:
            out_node = node.parm("soppath").evalAsNode()

        elif node_type == "alembic":

            # Alembic can switch between using SOP Path or object
            if node.parm("use_sop_path").eval():
                out_node = node.parm("sop_path").evalAsNode()
            else:
                root = node.parm("root").eval()
                objects = node.parm("objects").eval()
                path = root + "/" + objects
                out_node = hou.node(path)

        elif node_type == "comp":
            out_node = node.parm("coppath").evalAsNode()

        elif node_type == "usd" or node_type == "usdrender":
            out_node = node.parm("loppath").evalAsNode()

        elif node_type == "usd_rop" or node_type == "usdrender_rop":
            # Inside Solaris e.g. /stage (not in ROP context)
            # When incoming connection is present it takes it directly
            inputs = node.inputs()
            if inputs:
                out_node = inputs[0]
            else:
                out_node = node.parm("loppath").evalAsNode()

        elif node_type == "Redshift_Proxy_Output":
            out_node = node.parm("RS_archive_sopPath").evalAsNode()

        elif node_type == "filmboxfbx":
            out_node = node.parm("startnode").evalAsNode()

        else:
            raise KnownPublishError(
                f"ROP node type '{node_type}' is not supported"
                f" for product base type '{instance.data['productBaseType']}'"
            )

        if not out_node:
            self.log.warning("No output node collected.")
            return

        self.log.debug("Output node: %s" % out_node.path())
        instance.data["output_node"] = out_node
