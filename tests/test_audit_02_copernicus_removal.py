"""Focused Houdini regressions; run with Houdini 21's hython and unittest."""

import ast
import types
import unittest
from pathlib import Path

import hou


CLIENT = Path(__file__).resolve().parents[1] / "client" / "ayon_houdini"


def source_function(relative_path, name, namespace, class_name=None):
    """Load one source function without requiring a running AYON server."""
    path = CLIENT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if class_name:
        parent = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == class_name)
    else:
        parent = tree
    function = next(n for n in parent.body if isinstance(n, ast.FunctionDef)
                    and n.name == name)
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec", dont_inherit=True), namespace)
    return namespace[name]


class Regressions(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear(suppress_save_prompt=True)

    def test_remove_preserves_siblings_and_unmanaged_network(self):
        obj = hou.node("/obj")
        root = obj.createNode("subnet", "AYON_CONTAINERS")
        get_network = source_function(
            "plugins/load/load_image_copernicus.py",
            "get_image_ayon_container",
            {"pipeline": types.SimpleNamespace(
                get_or_create_ayon_container=lambda: root),
             "COPNET_NAME": "COPNET",
             "MANAGED_COPNET_KEY": "ayon:managed_image_copnet"})
        network = get_network()
        self.assertEqual(network.userData("ayon:managed_image_copnet"), "1")
        first = network.createNode("file", "first")
        second = network.createNode("file", "second")
        artist = network.createNode("null", "artist")
        remove = source_function(
            "plugins/load/load_image_copernicus.py", "remove",
            {"pipeline": types.SimpleNamespace(AYON_CONTAINERS=root.path()),
             "COPNET_NAME": "COPNET",
             "MANAGED_COPNET_KEY": "ayon:managed_image_copnet"},
            "ImageCopernicusLoader")
        remove(None, {"node": first})
        self.assertIsNotNone(hou.node(second.path()))
        self.assertIsNotNone(hou.node(artist.path()))
        remove(None, {"node": second})
        self.assertIsNotNone(hou.node(artist.path()))
        artist.destroy()
        last = network.createNode("file", "last")
        remove(None, {"node": last})
        self.assertIsNone(root.node("COPNET"))
        unmanaged = root.createNode("copnet", "COPNET")
        last = unmanaged.createNode("file", "last")
        remove(None, {"node": last})
        self.assertIsNotNone(root.node("COPNET"))
        other = root.createNode("copnet", "other")
        last = other.createNode("file", "last")
        remove(None, {"node": last})
        self.assertIsNotNone(root.node("other"))



if __name__ == "__main__":
    unittest.main()
