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
            raise PublishError(f"Failed to save to disk '{node.path()}'")

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
        src_root_dir = os.path.dirname(filepath)

        # Used to compare resolved paths against
        filepath = Path(filepath)

        # We keep the relative paths to the USD file
        transfers = instance.data.setdefault("transfers", [])
        publish_root = instance.data["publishDir"]
        for src in paths:

            if filepath == Path(src):
                continue

            relative_path = os.path.relpath(src, start=src_root_dir)
            self.log.debug(f"Collected dependency: {relative_path}")
            dest = os.path.normpath(os.path.join(publish_root, relative_path))
            transfers.append((src, dest))
