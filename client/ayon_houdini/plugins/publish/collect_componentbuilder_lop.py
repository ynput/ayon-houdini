import os
from typing import List, Tuple
from pathlib import Path

import pyblish.api

from ayon_core.pipeline import AYONPyblishPluginMixin, PublishError
from ayon_houdini.api import plugin

import hou
from pxr import Sdf, UsdUtils


def compute_all_dependencies(
        filepath: str) -> Tuple[list[Sdf.Layer], list[str], list[str]]:
    """Compute all dependencies for the given USD file."""
    # Only separated here for better type hints on returned values
    return UsdUtils.ComputeAllDependencies(filepath)


class CollectComponentBuilderLOPs(plugin.HoudiniInstancePlugin,
                                  AYONPyblishPluginMixin):

    # Run after `CollectResourcesPath`
    order = pyblish.api.CollectorOrder + 0.496
    families = ["componentbuilder"]
    label = "Collect Componentbuilder LOPs"

    def process(self, instance):

        node = hou.node(instance.data["instance_node"])

        # Render the component builder LOPs
        # TODO: Do we want this? or use existing frames? Usually a Collector
        #  should not 'extract' but in this case we need the resulting USD
        #  file.
        node.cook(force=True)  # required to clear existing errors
        node.parm("execute").pressButton()

        errors = node.errors()
        if errors:
            for error in errors:
                self.log.error(error)
            raise PublishError(
                f"Failed to save to disk '{node.path()}'. "
                "Please fix your scene to ensure it renders correctly "
                "and re-publish. Check the log for more information."
            )

        # Define the main asset usd file
        filepath = node.evalParm("lopoutput")
        representations = instance.data.setdefault("representations", [])
        representations.append({
            "name": "usd",
            "ext": "usd",
            "files": os.path.basename(filepath),
            "stagingDir": os.path.dirname(filepath),
        })

        # Get all its files and dependencies
        # TODO: Ignore any files that are not 'relative' to the USD file
        layers, assets, unresolved_paths = compute_all_dependencies(filepath)
        paths: List[str] = []
        paths.extend(layer.realPath for layer in layers)
        paths.extend(assets)

        # Skip unresolved paths, but warn about them
        for unresolved in unresolved_paths:
            self.log.warning(f"Cannot be resolved: {unresolved}")

        self.log.debug(f"Collecting USD: {filepath}")

        # Used to compare resolved paths against
        raw_root_dir = Path(os.path.abspath(filepath)).parent
        filepath = Path(filepath).resolve()
        src_root_dir = filepath.parent

        # We keep the relative paths to the USD file
        transfers = instance.data.setdefault("transfers", [])
        publish_root = instance.data["publishDir"]
        for src in paths:

            src_path = Path(src).resolve()
            if filepath == src_path:
                continue

            relative_path = self._get_relative_dependency_path(
                src, src_path, raw_root_dir, src_root_dir
            )
            if relative_path is None:
                self.log.debug(
                    "Skipping external dependency outside component "
                    f"directory: {src}"
                )
                continue

            self.log.debug(f"Collected dependency: {relative_path}")
            dest = os.path.normpath(os.path.join(publish_root, relative_path))
            transfers.append((src, dest))

    @staticmethod
    def _get_relative_dependency_path(
        src: str,
        src_path: Path,
        raw_root_dir: Path,
        src_root_dir: Path,
    ):
        """Return path relative to component root, or None if external.

        Args:
            src: Dependency file path returned by USD.
            src_path: Resolved dependency path for containment verification.
            raw_root_dir: Normalized non-resolved component staging directory.
            src_root_dir: Resolved component staging directory.

        Returns:
            Relative path inside ``publishDir``, or ``None`` if outside.
        """
        try:
            src_path.relative_to(src_root_dir)
        except ValueError:
            return None

        norm_src_path = Path(os.path.abspath(src))
        try:
            # Preserve the authored layout for internal symlinks inside root
            return norm_src_path.relative_to(raw_root_dir)
        except ValueError:
            # Handle raw vs resolved component root mismatches (e.g. Windows
            # 8.3 short/long paths or an external symlinked parent folder)
            for parent in norm_src_path.parents:
                if (
                    not parent.is_symlink()
                    and parent.resolve() == src_root_dir
                ):
                    return norm_src_path.relative_to(parent)
            return None
