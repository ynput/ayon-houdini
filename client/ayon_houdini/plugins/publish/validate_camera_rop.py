# -*- coding: utf-8 -*-
"""Validator plugin for Houdini Camera ROP settings."""
import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import plugin


class ValidateCameraROP(plugin.HoudiniInstancePlugin):
    """Validate the Alembic ROP exports exactly one camera.

    The Alembic ROP of a camera instance must meet these criteria:

    - 'Use SOP Path' is disabled.
    - 'Root' is set to an object network, e.g. `/obj`.
    - 'Objects' is set to a single object, without patterns.
    - That object exists inside the root and is a camera.
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
        if not root_node:
            raise PublishValidationError(
                "Root parameter must be set on Alembic ROP",
                title=self.label)
        if root_node.childTypeCategory() != hou.objNodeTypeCategory():
            raise PublishValidationError(
                "Root parameter must be an object network, e.g. /obj. "
                f"Got: {root_node.path()} "
                f"(type: {root_node.childTypeCategory().name()})",
                title=self.label)

        # The Alembic ROP resolves objects against the top-most object
        # network in the Root path, e.g. `/obj` for Root `/obj/cameras`
        path = ""
        for name in root_node.path().split("/")[1:-1]:
            path += "/" + name
            parent = hou.node(path)
            if parent.childTypeCategory() == hou.objNodeTypeCategory():
                root_node = parent
                break

        objects = node.parm("objects").eval()
        errors = []
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
        elif (
            objects.startswith("/")
            and not objects.startswith(f"{root_node.path()}/")
        ):
            errors.append(
                "Objects parameter must be below Root when it starts with "
                f"a slash. Got: {objects} (Root: {root_node.path()})")

        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishValidationError(
                "Some checks failed, see validator log.",
                title=self.label)

        camera = root_node.node(objects)
        if not camera:
            raise PublishValidationError(
                f"Camera path {objects} does not exist below "
                f"Root {root_node.path()}",
                title=self.label)

        if camera.type().name() != "cam":
            raise PublishValidationError(
                (f"Object set in Alembic ROP is not a camera: "
                 f"{camera} (type: {camera.type().name()})"),
                title=self.label)
