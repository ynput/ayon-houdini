from typing import Optional
import hou

from ayon_core.lib import EnumDef
from ayon_core.pipeline import get_representation_path

from ayon_houdini.api import (
    pipeline,
    plugin
)
from ayon_houdini.api.lib import (
    set_camera_resolution,
    get_camera_from_container
)


ARCHIVE_EXPRESSION = ('__import__("_alembic_hom_extensions")'
                      '.alembicGetCameraDict')


def get_expression(parm: hou.Parm) -> Optional[str]:
    try:
        return parm.expression()
    except hou.OperationFailed:
        # No expression present
        pass


def transfer_non_default_values(src, dest, ignore=None):
    """Copy parm from src to dest.

    Because the Alembic Archive rebuilds the entire node
    hierarchy on triggering "Build Hierarchy" we want to
    preserve any local tweaks made by the user on the camera
    for ease of use. That could be a background image, a
    resolution change or even Redshift camera parameters.

    We try to do so by finding all Parms that exist on both
    source and destination node, include only those that both
    are not at their default value, they must be visible,
    we exclude those that have the special "alembic archive"
    channel expression and ignore certain Parm types.

    """

    ignore_types = {
        hou.parmTemplateType.Toggle,
        hou.parmTemplateType.Menu,
        hou.parmTemplateType.Button,
        hou.parmTemplateType.FolderSet,
        hou.parmTemplateType.Separator,
        hou.parmTemplateType.Label,
    }

    src.updateParmStates()

    for parm in src.allParms():

        if ignore and parm.name() in ignore:
            continue

        # If destination parm does not exist, ignore..
        dest_parm = dest.parm(parm.name())
        if not dest_parm:
            continue

        # Ignore values that are currently at default
        if parm.isAtDefault() and dest_parm.isAtDefault():
            continue

        if not parm.isVisible():
            # Ignore hidden parameters, assume they
            # are implementation details
            continue

        expression = get_expression(parm)
        if expression is not None and ARCHIVE_EXPRESSION in expression:
            # Assume it's part of the automated connections that the
            # Alembic Archive makes on loading of the camera and thus we do
            # not want to transfer the expression
            continue

        # Ignore folders, separators, etc.
        if parm.parmTemplate().type() in ignore_types:
            continue

        print("Preserving attribute: %s" % parm.name())
        dest_parm.setFromParm(parm)


class CameraLoader(plugin.HoudiniLoader):
    """Load camera from an Alembic file"""

    product_types = {"camera"}
    label = "Load Camera (abc)"
    representations = {"abc"}
    order = -10

    icon = "code-fork"
    color = "orange"

    camera_aperture_expression = "default"

    _match_maya_render_mask_expression = """
# Match maya render mask (logic from Houdini's own FBX importer)
node = hou.pwd()
resx = node.evalParm('resx')
resy = node.evalParm('resy')
aspect = node.evalParm('aspect')
aperture *= min(1, (resx / resy * aspect) / 1.5)
return aperture
"""

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef(
                "cameraApertureExpression",
                label="Camera Aperture Expression",
                items=[
                    {"label": "Houdini Default", "value": "default"},
                    {"label": "Match Maya render mask", "value": "match_maya"}
                ],
                default=cls.camera_aperture_expression,
                tooltip=(
                    "Set the aperture expression on the camera from the "
                    "Alembic using either:\n"
                    "- Houdini default expression\n"
                    "- Match the Maya render mask (which matches Houdini's "
                    "FBX Import camera expression."
                )
            )
        ]

    def load(self, context, name=None, namespace=None, options=None):

        # Format file name, Houdini only wants forward slashes
        file_path = self.filepath_from_context(context).replace("\\", "/")

        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["folder"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create a archive node
        node = self.create_and_connect(obj, "alembicarchive", node_name)

        # TODO: add FPS of project / folder
        node.setParms({"fileName": file_path, "channelRef": True})

        # Apply some magic
        node.parm("buildHierarchy").pressButton()
        node.moveToGoodPosition()

        # Create an alembic xform node
        nodes = [node]

        camera = get_camera_from_container(node)

        if options.get("cameraApertureExpression",
                       self.camera_aperture_expression) == "match_maya":
            self._match_maya_render_mask(camera)

        set_camera_resolution(camera, entity=context["folder"])
        self[:] = nodes

        return pipeline.containerise(node_name,
                                     namespace,
                                     nodes,
                                     context,
                                     self.__class__.__name__,
                                     suffix="")

    def update(self, container, context):
        repre_entity = context["representation"]
        node = container["node"]

        # Update the file path
        file_path = get_representation_path(repre_entity)
        file_path = file_path.replace("\\", "/")

        # Update attributes
        node.setParms({"fileName": file_path,
                       "representation": repre_entity["id"]})

        # Store the cam temporarily next to the Alembic Archive
        # so that we can preserve parm values the user set on it
        # after build hierarchy was triggered.
        old_camera = get_camera_from_container(node)
        temp_camera = old_camera.copyTo(node.parent())

        # Rebuild
        node.parm("buildHierarchy").pressButton()

        # Apply values to the new camera
        new_camera = get_camera_from_container(node)
        transfer_non_default_values(temp_camera,
                                    new_camera,
                                    # The hidden uniform scale attribute
                                    # gets a default connection to
                                    # "icon_scale" just skip that completely
                                    ignore={"scale"})

        # Detect whether the camera was loaded with the "Match Maya render
        # mask" before. If so, we want to maintain that expression on update.
        if (
                self._match_maya_render_mask_expression
                in get_expression(temp_camera.parm("aperture"))
        ):
            self._match_maya_render_mask(new_camera)

        set_camera_resolution(new_camera)

        temp_camera.destroy()

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):

        node = container["node"]
        node.destroy()

    def create_and_connect(self, node, node_type, name=None):
        """Create a node within a node which and connect it to the input

        Args:
            node(hou.Node): parent of the new node
            node_type(str) name of the type of node, eg: 'alembic'
            name(str, Optional): name of the node

        Returns:
            hou.Node

        """
        if name:
            new_node = node.createNode(node_type, node_name=name)
        else:
            new_node = node.createNode(node_type)

        new_node.moveToGoodPosition()
        return new_node

    def _match_maya_render_mask(self, camera):
        """Workaround to match Maya render mask in Houdini"""
        parm = camera.parm("aperture")
        print(f"Applying match Maya render mask expression to: {parm.path()}")

        expression = parm.expression()
        expression = expression.replace("return ", "aperture = ")
        expression += self._match_maya_render_mask_expression
        parm.setExpression(expression, language=hou.exprLanguage.Python)
