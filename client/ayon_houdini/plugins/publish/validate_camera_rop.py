# -*- coding: utf-8 -*-
"""Validator plugin for Houdini Camera ROP settings."""
import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import plugin


class ValidateCameraROP(plugin.HoudiniInstancePlugin):
    """Validate the Alembic ROP exports exactly one camera.

    The Alembic ROP of a camera instance must meet these criteria:

    - 'Use SOP Path' is disabled.
    - 'Root' is set and is not `/`.
    - 'Objects' is set to a single object, without patterns or relative
      parts like `..`.
    - That object exists below 'Root', with only object networks
      in between, and is a camera. Only `cam` nodes are supported.
    """

    order = pyblish.api.ValidatorOrder
    families = ["camera"]
    label = "Validate Camera ROP"

    # Houdini pattern characters, e.g. `cameras/*` or `@bundle`
    pattern_chars = ("*", "?", "[", "^", "@")

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
        elif any(part.startswith(".") for part in objects.split("/")):
            # Node names can't start with a dot, e.g. `..` or `.`
            errors.append(
                "Objects parameter must not use relative parts like `..`. "
                f"Got: {objects}")
        elif (
            root_node
            and objects.startswith("/")
            and not objects.startswith(f"{root_node.path()}/")
        ):
            errors.append(
                "Objects parameter starts with a slash but isn't an absolute "
                f"path below Root. Got: {objects} (Root: {root_node.path()})")

        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishValidationError(
                "Some checks failed, see validator log.",
                title=self.label)

        obj_category = hou.objNodeTypeCategory()
        if objects.startswith("/"):
            camera = hou.node(objects)
        else:
            # The Alembic ROP resolves relative objects against the
            # top-most object network at or above Root, e.g. `/obj` for
            # Root `/obj/cameras`
            obj_network = root_node
            while (
                obj_network
                and obj_network.childTypeCategory() != obj_category
            ):
                obj_network = obj_network.parent()
            while (
                obj_network
                and obj_network.parent()
                and obj_network.parent().childTypeCategory() == obj_category
            ):
                obj_network = obj_network.parent()
            if not obj_network:
                raise PublishValidationError(
                    f"Objects parameter {objects} must be an absolute path, "
                    f"Root {root_node.path()} is not in an object network.",
                    title=self.label)
            camera = obj_network.node(objects)

        if not camera:
            raise PublishValidationError(
                f"Camera path {objects} does not exist "
                f"(Root: {root_node.path()})",
                title=self.label)

        if not camera.path().startswith(f"{root_node.path()}/"):
            raise PublishValidationError(
                f"Camera {camera.path()} must be below "
                f"Root {root_node.path()}",
                title=self.label)

        # The ROP skips cameras below a non-object network, e.g. a LOP
        # network between Root and the camera
        parent = camera.parent()
        while parent != root_node:
            if parent.childTypeCategory() != obj_category:
                raise PublishValidationError(
                    f"Camera {camera.path()} must only have object networks "
                    f"between it and Root {root_node.path()}. "
                    f"Got: {parent.path()}",
                    title=self.label)
            parent = parent.parent()

        if camera.type().name().lower() not in {
            "cam", "agentcam", "stereocam", "stereocamrig",
            "vrcam", "lopimportcam"
        }:
            raise PublishValidationError(
                (f"Object set in Alembic ROP is not a camera: "
                 f"{camera} (type: {camera.type().name()})"),
                title=self.label)
