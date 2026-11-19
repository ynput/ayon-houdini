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
        filepath = Path(filepath).resolve()
        src_root_dir = filepath.parent

        # We keep the relative paths to the USD file
        transfers = instance.data.setdefault("transfers", [])
        publish_root = instance.data["publishDir"]
        for src in paths:

            src_path = Path(src).resolve()
            if filepath == src_path:
                continue

            try:
                relative_path = src_path.relative_to(src_root_dir)
            except ValueError:
                self.log.debug(
                    "Skipping external dependency outside component "
                    f"directory: {src}"
                )
                continue

            self.log.debug(f"Collected dependency: {relative_path}")
            dest = os.path.normpath(os.path.join(publish_root, relative_path))
            transfers.append((src, dest))
