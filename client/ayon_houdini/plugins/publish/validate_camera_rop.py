# -*- coding: utf-8 -*-
"""Validator plugin for Houdini Camera ROP settings."""
import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import lib, plugin


class ValidateCameraROP(plugin.HoudiniInstancePlugin):
    """Validate the Alembic ROP exports exactly one camera.

    The Alembic ROP of a camera instance must meet these criteria:

    - 'Use SOP Path' is disabled.
    - 'Root' is set and is not `/`.
    - 'Objects' is set to a single object, without patterns.
    - 'Root' and 'Objects' resolve to a camera the ROP exports,
      see `lib.get_camera_from_alembic_rop`. Camera types are `cam`,
      `agentcam`, `stereocam`, `stereocamrig`, `vrcam` and `lopimportcam`.
    """

    order = pyblish.api.ValidatorOrder
    families = ["camera"]
    label = "Validate Camera ROP"

    # Houdini pattern characters, e.g. `cameras/*` or `@bundle`
    pattern_chars = ("*", "?", "[", "^", "@")
    camera_types = {
        "cam", "agentcam", "stereocam", "stereocamrig",
        "vrcam", "lopimportcam"
    }

    def process(self, instance):

        import hou

        node = hou.node(instance.data.get("instance_node"))
        if node.parm("use_sop_path").eval():
            raise PublishValidationError(
                ("Alembic ROP for Camera export should not be "
                 "set to 'Use Sop Path'. Please disable."),
                title=self.label
            )

        # Get the root and objects parameter of the Alembic ROP node
        root_node = node.parm("root").evalAsNode()
        objects = node.parm("objects").eval()
        errors = []
        if not root_node:
            errors.append("Root parameter must be set on Alembic ROP")
        elif root_node.path() == "/":
            errors.append("Root parameter must not be /, e.g. use /obj")

        if not objects:
            errors.append("Objects parameter must be set on Alembic ROP")
        elif len(objects.split()) != 1:
            errors.append(
                f"Objects parameter must have a single object. Got: {objects}")
        elif any(char in objects for char in self.pattern_chars):
            # A pattern may match one camera now, but more once cameras
            # are added to the scene.
            errors.append(
                "Objects parameter must not use patterns, set the "
                f"camera path explicitly. Got: {objects}")

        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishValidationError(
                "Some checks failed, see validator log.",
                title=self.label)

        camera = lib.get_camera_from_alembic_rop(node)
        if camera is None:
            raise PublishValidationError(
                f"Root {root_node.path()} and Objects {objects} don't "
                "resolve to a camera the Alembic ROP exports. Objects must "
                "be an absolute path, or relative to the object network "
                "containing Root (e.g. Root /obj and Objects cameras/cam1), "
                "and the camera must be below Root.",
                title=self.label)

        if camera.type().name().lower() not in self.camera_types:
            raise PublishValidationError(
                (f"Object set in Alembic ROP is not a camera: "
                 f"{camera.path()} (type: {camera.type().name()})"),
                title=self.label)
