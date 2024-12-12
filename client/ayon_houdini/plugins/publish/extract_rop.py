import os
import pyblish.api

from ayon_core.pipeline import publish
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import splitext


class ExtractROP(plugin.HoudiniExtractorPlugin):
    """Generic Extractor for any ROP node."""
    label = "Extract ROP"
    order = pyblish.api.ExtractorOrder

    families = ["abc", "camera", "bgeo", "pointcache", "fbx",
                "vdbcache", "ass", "redshiftproxy", "mantraifd"]
    targets = ["local", "remote"]

    def process(self, instance: pyblish.api.Instance):
        if instance.data.get("farm"):
            self.log.debug("Should be processed on farm, skipping.")
            return
        creator_attribute = instance.data["creator_attributes"]

        files = instance.data["frames"]
        first_file = files[0] if isinstance(files, (list, tuple)) else files
        _, ext = splitext(
            first_file, allowed_multidot_extensions=[
                ".ass.gz", ".bgeo.sc", ".bgeo.gz",
                ".bgeo.lzma", ".bgeo.bz2"]
        )
        ext = ext.lstrip(".")

        # Value `local` is used as a fallback if the `render_target` key is missing.
        # This key might be absent because render targets are not yet implemented
        #  for all product types that use this plugin.
        if creator_attribute.get("render_target", "local") == "local":
            self.render_rop(instance)
        self.validate_expected_frames(instance)

        # In some cases representation name is not the the extension
        # TODO: Preferably we remove this very specific naming
        product_type = instance.data["productType"]
        name = {
            "bgeo": "bgeo",
            "rs": "rs",
            "ass": "ass"
        }.get(product_type, ext)

        representation = {
            "name": name,
            "ext": ext,
            "files": instance.data["frames"],
            "stagingDir": instance.data["stagingDir"],
            "frameStart": instance.data["frameStartHandle"],
            "frameEnd": instance.data["frameEndHandle"],
        }
        self.update_representation_data(instance, representation)
        instance.data.setdefault("representations", []).append(representation)

    def validate_expected_frames(self, instance: pyblish.api.Instance):
        """
        Validate all expected files in `instance.data["frames"]` exist in
        the staging directory.
        """
        filenames = instance.data["frames"]
        staging_dir = instance.data["stagingDir"]
        if isinstance(filenames, str):
            # Single frame
            filenames = [filenames]

        missing_filenames = [
            filename for filename in filenames
            if not os.path.isfile(os.path.join(staging_dir, filename))
        ]
        if missing_filenames:
            raise RuntimeError(f"Missing frames: {missing_filenames}")

    def update_representation_data(self,
                                   instance: pyblish.api.Instance,
                                   representation: dict):
        """Allow subclass to override the representation data in-place"""
        pass


class ExtractOpenGLAndFlipbook(ExtractROP,
                               publish.ColormanagedPyblishPluginMixin):

    order = pyblish.api.ExtractorOrder - 0.01
    label = "Extract Review (OpenGL & Flipbook)"
    families = ["rop.opengl"]

    def update_representation_data(self,
                                   instance: pyblish.api.Instance,
                                   representation: dict):
        tags = ["review"]
        if not instance.data.get("keepImages"):
            tags.append("delete")

        representation.update({
            # TODO: Avoid this override?
            "name": instance.data["imageFormat"],
            "ext": instance.data["imageFormat"],

            "tags": tags,
            "preview": True,
            "camera_name": instance.data.get("review_camera")
        })


class ExtractComposite(ExtractROP,
                       publish.ColormanagedPyblishPluginMixin):

    label = "Extract Composite (Image Sequence)"
    families = ["imagesequence"]

    def update_representation_data(self,
                                   instance: pyblish.api.Instance,
                                   representation: dict):

        if representation["ext"].lower() != "exr":
            return

        # Inject colorspace with 'scene_linear' as that's the
        # default Houdini working colorspace and all extracted
        # OpenEXR images should be in that colorspace.
        # https://www.sidefx.com/docs/houdini/render/linear.html#image-formats
        self.set_representation_colorspace(
            representation, instance.context,
            colorspace="scene_linear"
        )
