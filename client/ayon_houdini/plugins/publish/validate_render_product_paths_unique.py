import inspect
from collections import defaultdict
from typing import Dict, List

import pyblish.api
import clique
import hou

from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectInvalidAction


def get_instance_expected_files(instance: pyblish.api.Instance) -> List[str]:
    """Get the expected source render files for the instance."""
    # Prefer 'expectedFiles' over 'frames' because it usually contains more
    # output files than just a single file or single sequence of files.
    expected_files: List[Dict[str, List[str]]] = (
        instance.data.get("expectedFiles", [])
    )
    filepaths: List[str] = []
    if expected_files:
        # Products with expected files
        # This can be Render products or submitted cache to farm.
        for expected in expected_files:
            for sequence_files in expected.values():
                filepaths.extend(sequence_files)
    else:
        # Products with frames or single file.
        staging_dir = instance.data.get("stagingDir")
        frames = instance.data.get("frames")
        if frames is None or not staging_dir:
            return []

        if isinstance(frames, str):
            # single file.
            filepaths.append(f"{staging_dir}/{frames}")
        else:
            # list of frames
            filepaths.extend(f"{staging_dir}/{frame}" for frame in frames)

    return filepaths


class ValidateRenderProductPathsUnique(plugin.HoudiniContextPlugin,
                                       OptionalPyblishPluginMixin):
    """Validate that render product paths are unique.

    This allows to catch before rendering whether multiple render ROPs would
    end up writing to the same filepaths. This can be a problem when rendering
    because each render job would overwrite the files of the other at
    rendertime.

    """
    order = pyblish.api.ValidatorOrder
    families = [
        # Render products
        "usdrender", "karma_rop", "redshift_rop", "arnold_rop", "mantra_rop",

        # Product families from collect frames plug-in
        "camera", "vdbcache", "imagesequence", "ass", "redshiftproxy",
        "review", "pointcache", "fbx", "model"
    ]

    hosts = ["houdini"]
    label = "Unique Render Product Paths"
    actions = [SelectInvalidAction]
    optional = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        invalid = self.get_invalid(context)
        if not invalid:
            return

        node_paths = [node.path() for node in invalid]
        node_paths.sort()
        invalid_list = "\n".join(f"- {path}" for path in node_paths)
        raise PublishValidationError(
            "Multiple instances render to the same path. "
            "Please make sure each ROP renders to a unique output path:\n"
            f"{invalid_list}",
            title=self.label,
            description=self.get_description()
        )

    @classmethod
    def get_invalid(cls, context) -> "List[hou.Node]":
        # Get instances matching this plugin families
        instances = pyblish.api.instances_by_plugin(list(context), cls)
        if not instances:
            return []

        # Get expected rendered filepaths
        paths_to_instance_id = defaultdict(list)
        for instance in instances:
            # Skip the original instance when local rendering and those have
            # created additional runtime instances per AOV. This avoids
            # validating similar instances multiple times.
            if not instance.data.get("integrate", True):
                continue

            for filepath in get_instance_expected_files(instance):
                paths_to_instance_id[filepath].append(instance.id)

        # Get invalid instances by instance.id
        invalid_instance_ids = set()
        invalid_paths = []
        for path, path_instance_ids in paths_to_instance_id.items():
            if len(path_instance_ids) > 1:
                for path_instance_d in path_instance_ids:
                    invalid_instance_ids.add(path_instance_d)
                invalid_paths.append(path)

        if not invalid_instance_ids:
            return []

        # Log invalid sequences as single collection
        collections, remainder = clique.assemble(invalid_paths)
        for collection in collections:
            cls.log.warning(f"Multiple instances output to path: {collection}")
        for path in remainder:
            cls.log.warning(f"Multiple instances output to path: {path}")

        # Get the invalid instances so we could also add a select action.
        invalid = []
        for instance in [
            instance for instance in instances
            if instance.id in invalid_instance_ids
        ]:
            node = hou.node(instance.data["instance_node"])
            invalid.append(node)

        return invalid

    def get_description(self):
        return inspect.cleandoc(
            """### Output paths overwrite each other
            
            Multiple instances output to the same path. This can cause each
            render to overwrite the other providing unexpected results.
            
            Update the output paths to be unique across all instances.
            
            It may be the case that a single instance outputs multiple files
            that overwrite each other, like separate AOV outputs from one ROP.
            In that case it may be necessary to update the individual AOV 
            output paths, instead of outputs between separate instances.
            """
        )
