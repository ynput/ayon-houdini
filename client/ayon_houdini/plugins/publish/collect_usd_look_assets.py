import re

import itertools
import os
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import dataclasses

import pyblish.api

from pxr import Sdf

from ayon_houdini.api import plugin
from ayon_houdini.api.usd import get_layer_save_path


# Colorspace attributes differ per renderer implementation in the USD data
# Some have dedicated input names like Arnold and Redshift, whereas others like
# MaterialX store `colorSpace` metadata on the asset property itself.
# See `get_colorspace` method on the plug-in for more details
COLORSPACE_ATTRS = [
    "inputs:color_space",        # Image Vop (arnold::image)
    "inputs:tex0_colorSpace",    # RS Texture Vop (redshift::TextureSampler)
    # TODO: USD UV Texture VOP doesn't seem to use colorspaces from the actual
    #  OCIO configuration so we skip these for now. Especially since the
    #  texture is usually used for 'preview' purposes anyway.
    # "inputs:sourceColorSpace",   # USD UV Texture Vop (usduvtexture::2.0)
]


@dataclasses.dataclass
class Resource:
    attribute: str            # property path
    source: str               # unresolved source path
    files: List[str]          # resolve list of files, e.g. multiple for <UDIM>
    color_space: str = None   # colorspace of the resource
    relative_dir: str = ""    # optional subfolder under resourcesDir
    resolved_source: Optional[str] = None  # anchored path for relative sources


def get_layer_property_paths(layer: Sdf.Layer) -> List[Sdf.Path]:
    """Return all property paths from a layer"""
    paths = []

    def collect_paths(path):
        if not path.IsPropertyPath():
            return
        paths.append(path)

    layer.Traverse("/", collect_paths)

    return paths


class CollectUsdLookAssets(plugin.HoudiniInstancePlugin):
    """Collect all assets introduced by the look.

    We are looking to collect e.g. all texture resources so we can transfer
    them with the publish and write then to the publish location.

    If possible, we'll also try to identify the colorspace of the asset.

    """
    # TODO: Implement $F frame support (per frame values)
    # TODO: If input image is already a published texture or resource than
    #   preferably we'd keep the link in-tact and NOT update it. We can just
    #   start ignoring AYON URIs

    label = "Collect USD Look Assets"
    order = pyblish.api.CollectorOrder
    hosts = ["houdini"]
    families = ["look"]

    exclude_suffixes = [".usd", ".usda", ".usdc", ".usdz", ".abc", ".vdb"]

    def process(self, instance):

        # Get Sdf.Layers from "Collect ROP Sdf Layers and USD Stage" plug-in
        layers = instance.data.get("layers")
        if layers is None:
            self.log.warning(f"No USD layers found on instance: {instance}")
            return

        layers: List[Sdf.Layer]
        instance_resources = self.get_layer_assets(layers)

        # Define a relative asset remapping for the USD Extractor so that
        # any textures are remapped to their 'relative' publish path.
        # All textures will be in a relative `./resources/` folder, placing
        # colliding filenames in numbered subfolders to avoid overwrites.
        remap = {}
        used_sources: Dict[Path, Tuple[Path, str]] = {}
        used_targets: Dict[Path, Path] = {}
        for resource in instance_resources:
            source_name = Path(resource.source.replace("\\", "/")).name
            canonical_source = Path(
                os.path.normpath(resource.resolved_source or resource.source)
            )
            file_paths = [Path(os.path.normpath(f)) for f in resource.files]
            rel_dir = self._find_unique_relative_dir(
                source_name,
                canonical_source,
                file_paths,
                used_sources,
                used_targets,
            )
            resource.relative_dir = rel_dir

            source_key = Path(rel_dir) / source_name
            winning_name = used_sources.get(
                source_key, (canonical_source, source_name)
            )[1]
            used_sources[source_key] = (canonical_source, winning_name)
            for path in file_paths:
                used_targets[Path(rel_dir) / path.name] = path

            rel_path = Path(rel_dir) / winning_name
            target_path = f"./resources/{rel_path.as_posix()}"
            remap.setdefault(os.path.normpath(resource.source), target_path)
            if resource.resolved_source:
                remap[os.path.normpath(resource.resolved_source)] = target_path
        instance.data["assetRemap"] = remap

        # Store resources on instance
        resources = instance.data.setdefault("resources", [])
        for resource in instance_resources:
            resources.append(dataclasses.asdict(resource))

        # Log all collected textures
        # Note: It is fine for a single texture to be included more than once
        # where even one of them does not have a color space set, but the other
        # does. For example, there may be a USD UV Texture just for a GL
        # preview material which does not specify an OCIO color
        # space.
        all_files = []
        for resource in instance_resources:
            all_files.append(f"{resource.attribute}:")

            for filepath in resource.files:
                if resource.color_space:
                    file_label = f"- {filepath} ({resource.color_space})"
                else:
                    file_label = f"- {filepath}"
                all_files.append(file_label)

        if all_files:
            self.log.info(
                "Collected assets:\n{}".format(
                    "\n".join(all_files)
                )
            )
        else:
            self.log.debug("Collected no assets")

    def get_layer_assets(self, layers: List[Sdf.Layer]) -> List[Resource]:
        # TODO: Correctly resolve paths using Asset Resolver.
        #       Preferably this would use one cached
        #       resolver context to optimize the path resolving.
        # TODO: Fix for timesamples - if timesamples, then `.default` might
        #       not be authored on the spec

        resources: List[Resource] = list()
        for layer in layers:
            for path in get_layer_property_paths(layer):

                spec = layer.GetAttributeAtPath(path)
                if not spec:
                    continue

                if spec.typeName != "asset":
                    continue

                # Skip Houdini procedurals
                if self._is_houdini_procedural_path(path):
                    continue

                if spec.default is None:
                    # This may happen if no default value is authored. Likely
                    # the property is animated or only custom metadata is set
                    # for the property's opinion.
                    # TODO: Support detecting animated asset path values
                    #  Houdini makes it non-trivial
                    #  to key material parameters so for now we'll assume the
                    #  user did not animate asset paths making this low prio.
                    self.log.debug(
                        f"Skipping spec {path} due to no default value."
                    )
                    continue

                asset: Sdf.AssetPath = spec.default
                if not asset.path:
                    continue

                base, ext = os.path.splitext(asset.path)
                if ext in self.exclude_suffixes:
                    continue

                filepath = asset.path.replace("\\", "/")

                # Skip AYON entity URIs because these represent already
                # published files.
                if filepath.startswith(("ayon://", "ayon+entity://")):
                    self.log.debug(
                        "Skipping AYON Entity URI at "
                        f"'{path}': {filepath}"
                    )
                    continue

                # Anchor relative paths to absolute paths
                resolved_source = None
                if filepath.startswith(("./", "../")):
                    # USD can't anchor to anonymous layers because it doesn't
                    # know where it exists - however, Houdini layers can have
                    # dedicated save paths, and hence could resolve paths
                    # relative to that.
                    if layer.anonymous:
                        layer_path = get_layer_save_path(layer)
                        if layer_path:
                            folder = Path(layer_path).parent
                            filepath = (folder / filepath).as_posix()
                        else:
                            self.log.warning(
                                "Skipping asset with relative path."
                                " USD layer's path is unknown so"
                                " we cannot resolve the full path for"
                                f" attribute '{path}': {filepath}"
                            )
                            continue
                    else:
                        filepath = Sdf.ComputeAssetPathRelativeToLayer(
                            layer, filepath
                        )
                    resolved_source = filepath

                # Expand <UDIM> to all files of the available files on disk
                # TODO: Add support for `<TILE>`
                # TODO: Add support for `<ATTR:name INDEX:name DEFAULT:value>`
                if "<UDIM>" in filepath.upper():
                    parts = re.split(
                        r"<UDIM>", filepath, flags=re.IGNORECASE
                    )
                    pattern = ("[0-9]" * 4).join(
                        glob.escape(part) for part in parts
                    )
                    files = glob.glob(pattern)
                else:
                    # Single file
                    files = [filepath]

                # Detect the colorspace of the input asset property
                colorspace = self.get_colorspace(spec)

                resource = Resource(
                    attribute=path.pathString,
                    source=asset.path,
                    files=files,
                    color_space=colorspace,
                    resolved_source=resolved_source,
                )
                resources.append(resource)

        # Sort by filepath
        resources.sort(key=lambda r: r.source)

        return resources

    @staticmethod
    def _find_unique_relative_dir(
        source_name: str,
        canonical_source: Path,
        file_paths: List[Path],
        used_sources: Dict[Path, Tuple[Path, str]],
        used_targets: Dict[Path, Path],
    ) -> str:
        """Return a collision-free subfolder under ``resourcesDir``.

        Args:
            source_name (str): Basename of the unresolved resource path.
            canonical_source (Path): Normalized canonical source path.
            file_paths (List[Path]): Normalized resolved concrete file paths.
            used_sources (dict): Relative source keys mapped to
                ``(canonical_source, winning_basename)``.
            used_targets (dict): Relative concrete file keys mapped to
                normalized source file paths.

        Returns:
            str: Relative subfolder name (empty string if root is free).
        """
        for sub_idx in itertools.count():
            rel_dir = str(sub_idx) if sub_idx else ""
            existing_src = used_sources.get(Path(rel_dir) / source_name)
            if existing_src and existing_src[0] != canonical_source:
                continue
            if any(
                used_targets.get(Path(rel_dir) / path.name)
                not in (None, path)
                for path in file_paths
            ):
                continue
            return rel_dir

    def _is_houdini_procedural_path(self, path: Sdf.Path) -> bool:
        """Return whether path represents a Houdini procedural asset path."""
        procedural_marker = "houdini:procedural:path"
        return procedural_marker in path.pathString

    def get_colorspace(self, spec: Sdf.AttributeSpec) -> Optional[str]:
        """Return colorspace for a Asset attribute spec.

        There is currently no USD standard on how colorspaces should be
        represented for shaders or asset properties - each renderer's material
        implementations seem to currently use their own way of specifying the
        colorspace on the shader. As such, this comes with some guesswork.

        Args:
            spec (Sdf.AttributeSpec): The asset type attribute to retrieve
                the colorspace for.

        Returns:
            Optional[str]: The colorspace for the given attribute, if any.

        """
        # TODO: Support Karma, V-Ray, Renderman texture colorspaces
        # Materialx image defines colorspace as custom info on the attribute
        if spec.HasInfo("colorSpace"):
            return spec.GetInfo("colorSpace")

        # Arnold materials define the colorspace as a separate primvar
        # TODO: Fix for timesamples - if timesamples, then `.default` might
        #       not be authored on the spec
        prim_path = spec.path.GetPrimPath()
        layer = spec.layer
        for name in COLORSPACE_ATTRS:
            colorspace_property_path = prim_path.AppendProperty(name)
            colorspace_spec = layer.GetAttributeAtPath(
                colorspace_property_path
            )
            if colorspace_spec and colorspace_spec.default:
                return colorspace_spec.default


class CollectUsdLookResourceTransfers(plugin.HoudiniInstancePlugin):
    """Define the publish direct file transfers for any found resources.

    This ensures that any source texture will end up in the published look
    in the `resourcesDir`.

    """
    label = "Collect USD Look Transfers"
    order = pyblish.api.CollectorOrder + 0.496
    hosts = ["houdini"]
    families = ["look"]

    def process(self, instance):

        resources_dir = Path(instance.data["resourcesDir"])
        transfers = instance.data.setdefault("transfers", [])
        seen = {
            (Path(os.path.normpath(src)), Path(os.path.normpath(dest)))
            for src, dest in transfers
        }
        for resource in instance.data.get("resources", []):
            dest_dir = resources_dir / resource["relative_dir"]
            for src in resource["files"]:
                dest = dest_dir / Path(src.replace("\\", "/")).name
                key = (Path(os.path.normpath(src)), dest)
                if key in seen:
                    continue
                seen.add(key)
                transfers.append((src, str(dest)))
                self.log.debug("Registering transfer: %s -> %s", src, dest)
