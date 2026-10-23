# -*- coding: utf-8 -*-
"""Validator plugin for Houdini Camera ROP settings."""
import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import plugin


class ValidateCameraROP(plugin.HoudiniInstancePlugin):
    """Validate the Alembic ROP exports exactly one camera.

    The Alembic ROP of a camera instance must meet these criteria:

    - 'Use SOP Path' is disabled.
    - 'Root' is set to an absolute path, e.g. `/obj`.
    - 'Objects' is set to a single object.
    - That object exists and is a camera.
    """

    order = pyblish.api.ValidatorOrder
    families = ["camera"]
    label = "Camera ROP"

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
        root = node.parm("root").eval()
        objects = node.parm("objects").eval()
        errors = []
        if not root:
            errors.append("Root parameter must be set on Alembic ROP")
        if not root.startswith("/"):
            errors.append("Root parameter must start with slash /")
        if not objects:
            errors.append("Objects parameter must be set on Alembic ROP")

        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishValidationError(
                "Some checks failed, see validator log.",
                title=self.label)

        # Resolve the 'Objects' value to absolute object paths. Houdini's own
        # parameter evaluation handles absolute paths and patterns, the
        # fallback resolves the value relative to 'Root'.
        object_paths = self.get_object_paths(node.parm("objects"), root)

        if len(object_paths) != 1:
            raise PublishValidationError(
                "'Objects' must resolve to exactly one object, "
                f"found {len(object_paths)}: "
                f"{object_paths or objects!r} (Root: {root!r})",
                title=self.label,
            )

        path = object_paths[0]
        camera = hou.node(path)
        # Check if the object exists and is a camera
        if not camera:
            raise PublishValidationError(
                "Camera path does not exist: %s" % path,
                title=self.label)

        if camera.type().name() != "cam":
            raise PublishValidationError(
                (f"Object set in Alembic ROP is not a camera: "
                 f"{camera} (type: {camera.type().name()})"),
                title=self.label)

    def get_object_paths(self, objects_parm, root) -> list[str]:
        """Return the object paths of the Alembic ROP 'Objects' parameter.

        The value is resolved by Houdini's own parameter evaluation first,
        which handles absolute paths and patterns (e.g. ``cameras/*``).
        Values Houdini does not resolve, e.g. when the parameter does not
        apply the 'root' parameter, are resolved relative to 'root' instead.

        Args:
            objects_parm (hou.Parm): The 'objects' parameter of the ROP.
            root (str): Value of the ROP 'root' parameter.

        Returns:
            list[str]: Absolute object paths, or an empty list when the value
                does not describe a single object. Paths are not checked for
                existence.
        """
        import hou

        try:
            object_paths = list(objects_parm.evalAsNodePaths())
        except (hou.Error, TypeError):
            object_paths = []
        if object_paths:
            return object_paths

        objects = objects_parm.eval() or ""
        root = (root or "").rstrip("/")

        # A pattern or bundle that Houdini did not resolve matches no object
        if any(char in objects for char in ("*", "?", "^", "@")):
            return []
        if not root.startswith("/"):
            return []

        object_paths = []
        for obj in objects.split():
            if obj.startswith("/"):
                object_paths.append(obj)
            else:
                object_paths.append("/".join(filter(None, [root, obj])))
        return object_paths
