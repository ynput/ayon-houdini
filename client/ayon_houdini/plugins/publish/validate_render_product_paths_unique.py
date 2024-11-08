import inspect
from collections import defaultdict
from typing import List

import pyblish.api
import clique
import hou

from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)

from ayon_houdini.api import plugin
from ayon_houdini.api.action import SelectInvalidAction


class ValidateRenderProductPathsUnique(plugin.HoudiniContextPlugin,
                                       OptionalPyblishPluginMixin):
    """Validate that render product paths are unique.

    This allows to catch before rendering whether multiple render ROPs would
    end up writing to the same filepaths. This can be a problem when rendering
    because each render job would overwrite the files of the other at
    rendertime.

    """
    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
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
        if len(instances) < 2:
            return []

        # Get expected rendered filepaths
        paths_to_instance_id = defaultdict(list)
        for instance in instances:
            expected_files = instance.data.get("expectedFiles", [])
            files_by_aov = expected_files[0]
            for aov_name, aov_filepaths in files_by_aov.items():
                for aov_filepath in aov_filepaths:
                    paths_to_instance_id[aov_filepath].append(instance.id)

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
            """
        )
