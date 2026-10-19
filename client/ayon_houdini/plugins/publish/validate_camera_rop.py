# -*- coding: utf-8 -*-
"""Validator plugin for Houdini Camera ROP settings."""
import pyblish.api
from ayon_core.pipeline import PublishValidationError

from ayon_houdini.api import plugin


class ValidateCameraROP(plugin.HoudiniInstancePlugin):
    """Validate Camera ROP settings."""

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
        if len(objects.split(" ")) != 1:
            errors.append("Must have only a single object.")

        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishValidationError(
                "Some checks failed, see validator log.",
                title=self.label)

        # check if there is only one object path
        object_paths = self.get_object_paths(root, objects)
        if len(object_paths) != 1:
            raise PublishValidationError(
                "Must have exactly one object path.",
                title=self.label)

        path = object_paths[0]
        camera = hou.node(path)
        # Check if the object exists and is a camera
        if not camera:
            raise PublishValidationError(
                "Camera path does not exist: %s" % path,
                title=self.label)

        if camera.type().name() != "cam":
            raise PublishValidationError(
                ("Object set in Alembic ROP is not a camera: "
                 "{} (type: {})").format(camera, camera.type().name()),
                title=self.label)

    def get_object_paths(self, root, objects) -> list[str]:
        """Get full object paths based on root and objects parameters.

        Args:
            root (str): The root path of the Alembic ROP.
            objects (str): The objects parameter of the Alembic ROP.

        Returns:
            list[str]: A list of full object paths.

        """
        root = root.rstrip("/")
        object_paths = []
        for obj in objects.split(" "):
            if not obj:
                continue

            if obj.startswith("/"):
                object_paths.append(obj)
            else:
                object_paths.append("/".join([root, obj]))

        return object_paths
