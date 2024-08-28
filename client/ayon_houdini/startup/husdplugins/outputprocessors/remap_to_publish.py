import os
import json

import hou
from husd.outputprocessor import OutputProcessor


_COMPATIBILITY_PLACEHOLDER = object()


class AYONRemapPaths(OutputProcessor):
    """Remap paths based on a mapping dict on rop node."""

    def __init__(self):
        self._mapping = dict()

    @staticmethod
    def name():
        return "ayon_remap_paths"

    @staticmethod
    def displayName():
        return "AYON Remap Paths"

    @staticmethod
    def hidden():
        return True

    @staticmethod
    def parameters():
        group = hou.ParmTemplateGroup()

        parm_template = hou.StringParmTemplate(
            "ayon_remap_paths_remap_json",
            "Remapping dict (json)",
            default_value="{}",
            num_components=1,
            string_type=hou.stringParmType.Regular,
        )
        group.append(parm_template)

        return group.asDialogScript()

    def beginSave(self,
                  config_node,
                  config_overrides,
                  lop_node,
                  t,
                  # Added in Houdini 20.5.182
                  stage_variables=_COMPATIBILITY_PLACEHOLDER):

        args = [config_node, config_overrides, lop_node, t]
        if stage_variables is not _COMPATIBILITY_PLACEHOLDER:
            args.append(stage_variables)
        super(AYONRemapPaths, self).beginSave(*args)

        value = config_node.evalParm("ayon_remap_paths_remap_json")
        mapping = json.loads(value)
        assert isinstance(self._mapping, dict)

        # Ensure all keys are normalized paths so the lookup can be done
        # correctly
        mapping = {
            os.path.normpath(key): value for key, value in mapping.items()
        }
        self._mapping = mapping

    def processReferencePath(self,
                             asset_path,
                             referencing_layer_path,
                             asset_is_layer):
        return self._mapping.get(os.path.normpath(asset_path), asset_path)


def usdOutputProcessor():
    return AYONRemapPaths
