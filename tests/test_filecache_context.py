import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


CLIENT = (
    Path(__file__).resolve().parents[1] / "client" / "ayon_houdini"
)


class ExistingInstance(dict):
    @classmethod
    def from_existing(cls, data, creator):
        instance = cls(data)
        instance.data = instance
        instance.creator = creator
        return instance


class FileCacheContextTests(unittest.TestCase):
    def setUp(self):
        self.node = Mock()
        self.node.path.return_value = "/obj/geo1/cache"
        self.data = {
            "AYON_CACHE_FOLDER_PATH": "/assets/tree",
            "AYON_CACHE_TASK": "modeling",
            "AYON_productName": "filecacheMain",
        }
        self.write = Mock()
        namespace = {
            "read": lambda node: self.data.copy(),
            "hou": SimpleNamespace(node=Mock(return_value=self.node)),
            "CreatedInstance": ExistingInstance,
            "imprint": self.write,
        }
        base_path = CLIENT / "api" / "plugin.py"
        base = next(
            item for item in ast.parse(base_path.read_text()).body
            if isinstance(item, ast.ClassDef)
            and item.name == "HoudiniCreator"
        )
        base.bases = []
        base.body = [
            item for item in base.body
            if isinstance(item, ast.FunctionDef)
            and item.name in {
                "collect_instances", "update_instances", "imprint"
            }
        ]
        exec(
            compile(ast.Module(body=[base], type_ignores=[]),
                    str(base_path), "exec"),
            namespace,
        )
        namespace["plugin"] = SimpleNamespace(
            HoudiniCreator=namespace["HoudiniCreator"]
        )
        namespace["CreatorError"] = RuntimeError
        creator_path = CLIENT / "plugins" / "create" / "create_file_cache.py"
        creator_code = ast.parse(creator_path.read_text())
        creator_code.body = [
            item for item in creator_code.body
            if not isinstance(item, (ast.Import, ast.ImportFrom))
        ]
        exec(compile(creator_code, str(creator_path), "exec"), namespace)
        self.creator = namespace["CreateFileCache"]()
        self.creator.cache_instance_data = Mock()
        self.creator.collection_shared_data = {
            "houdini_cached_instances": {
                self.creator.identifier: [self.node],
            },
        }
        self.creator._add_instance_to_context = Mock()

    def test_collection_restores_aliases_and_preserves_base_metadata(self):
        self.creator.collect_instances()
        instance = self.creator._add_instance_to_context.call_args.args[0]
        self.assertEqual(instance["folderPath"], "/assets/tree")
        self.assertEqual(instance["task"], "modeling")
        self.assertEqual(instance["productName"], "filecacheMain")
        self.assertEqual(instance["instance_node"], "/obj/geo1/cache")
        self.assertEqual(instance["instance_id"], "/obj/geo1/cache")
        self.assertEqual(instance["families"], ["filecache", "cache"])
        self.assertNotIn("AYON_CACHE_FOLDER_PATH", instance)
        self.assertNotIn("AYON_CACHE_TASK", instance)

    def test_collection_preserves_legacy_canonical_context(self):
        self.data.pop("AYON_CACHE_FOLDER_PATH")
        self.data.pop("AYON_CACHE_TASK")
        self.data.update(folderPath="/assets/legacy", task="lookdev")
        self.creator.collect_instances()
        instance = self.creator._add_instance_to_context.call_args.args[0]
        self.assertEqual(instance["folderPath"], "/assets/legacy")
        self.assertEqual(instance["task"], "lookdev")

    def test_updates_write_aliases_and_round_trip_new_context(self):
        instance = ExistingInstance(instance_node="/obj/geo1/cache")
        changes = {
            "folderPath": SimpleNamespace(new_value="/shots/010"),
            "task": SimpleNamespace(new_value="fx"),
            "productName": SimpleNamespace(new_value="filecacheFx"),
        }
        changes = type("Changes", (dict,), {})(changes)
        changes.changed_keys = set(changes)
        self.creator.update_instances([(instance, changes)])
        self.write.assert_called_once_with(
            self.node,
            {
                "AYON_CACHE_FOLDER_PATH": "/shots/010",
                "AYON_CACHE_TASK": "fx",
                "AYON_productName": "filecacheFx",
            },
            update=True,
        )
        self.data.update(self.write.call_args.args[1])
        self.creator.collect_instances()
        collected = self.creator._add_instance_to_context.call_args.args[0]
        self.assertEqual(collected["folderPath"], "/shots/010")
        self.assertEqual(collected["task"], "fx")


if __name__ == "__main__":
    unittest.main()
