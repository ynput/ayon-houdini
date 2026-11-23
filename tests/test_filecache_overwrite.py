import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "client"
    / "ayon_houdini"
    / "startup"
    / "otls"
    / "ayon_filecache.hda"
    / "ayon_8_8Sop_1Sop_1ayon__filecache_8_81.0"
    / "PythonModule"
)


class FileCacheOverwriteTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.settings = {
            "overwriteExisting": 0,
            "filemethod": 1,
            "trange": 1,
            "f1": 1001.0,
            "f2": 1002.0,
            "f3": 1.0,
            "substeps": 1,
            "useframeoverride": 0,
            "frameoverride": 1002.5,
            "resolvedPath": str(self.root),
        }
        self.output = Mock()
        self.output.evalAtFrame.side_effect = self.path_at_frame
        self.cache = Mock()
        self.cache.evalParm.side_effect = self.eval_cache_parm
        self.cache.parm.side_effect = lambda name: (
            self.output if name == "sopoutput" else self.buttons[name]
        )
        self.buttons = {"execute": Mock(), "cookoutputnode": Mock()}
        self.node = Mock()
        self.node.evalParm.side_effect = self.settings.__getitem__
        self.node.node.return_value = self.cache
        self.hou = SimpleNamespace(
            Error=RuntimeError,
            frame=Mock(return_value=1001.0),
            expandString=lambda value: value.replace(
                "$CACHE_ROOT", str(self.root)
            ).replace("$FF", "1001"),
            expandStringAtFrame=lambda value, frame: value.replace(
                "$CACHE_ROOT", str(self.root)
            ).replace("$FF", "{:g}".format(frame)),
        )
        self.module = {"hou": self.hou}
        exec(
            compile(MODULE_PATH.read_text(), str(MODULE_PATH), "exec"),
            self.module,
        )

    def path_at_frame(self, frame):
        return str(self.root / ("cache.{:g}.bgeo.sc".format(frame)))

    def eval_cache_parm(self, name):
        if name == "sopoutput":
            return self.path_at_frame(self.hou.frame())
        return self.settings[name]

    def test_existing_later_frame_blocks_both_saves(self):
        existing = Path(self.path_at_frame(1002))
        existing.write_text("original")
        for callback in ("save_cache", "save_background"):
            with self.subTest(callback=callback):
                with self.assertRaisesRegex(
                    RuntimeError, "Cache already exists"
                ):
                    self.module[callback](self.node)
        for button in self.buttons.values():
            button.pressButton.assert_not_called()
        self.assertFalse(Path(self.path_at_frame(1001)).exists())
        self.assertEqual(existing.read_text(), "original")

    def test_clear_range_and_overwrite_enabled_allow_both_saves(self):
        for overwrite in (0, 1):
            with self.subTest(overwrite=overwrite):
                self.settings["overwriteExisting"] = overwrite
                for callback in ("save_cache", "save_background"):
                    self.module[callback](self.node)
                Path(self.path_at_frame(1002)).touch()
        for button in self.buttons.values():
            self.assertEqual(button.pressButton.call_count, 2)

    def test_increment_and_substeps_only_check_written_frames(self):
        self.settings.update(f2=1005.0, f3=2.0)
        Path(self.path_at_frame(1002)).touch()
        self.module["save_cache"](self.node)
        self.assertEqual(
            [call.args[0] for call in self.output.evalAtFrame.call_args_list],
            [1001.0, 1003.0, 1005.0],
        )
        self.settings["substeps"] = 4
        Path(self.path_at_frame(1001.5)).touch()
        with self.assertRaises(RuntimeError):
            self.module["save_background"](self.node)
        self.buttons["cookoutputnode"].pressButton.assert_not_called()

    def test_single_frame_uses_current_or_override_frame(self):
        self.settings["trange"] = 0
        Path(self.path_at_frame(1002.5)).touch()
        self.module["save_cache"](self.node)
        self.output.evalAtFrame.assert_called_once_with(1001.0)
        self.settings["useframeoverride"] = 1
        with self.assertRaises(RuntimeError):
            self.module["save_background"](self.node)
        self.output.evalAtFrame.assert_called_with(1002.5)

    def test_remaining_variables_expand_at_output_frame(self):
        self.output.evalAtFrame.side_effect = None
        self.output.evalAtFrame.return_value = os.path.join(
            "$CACHE_ROOT", "cache.$FF.bgeo.sc"
        )
        Path(self.path_at_frame(1002)).touch()
        with self.assertRaises(RuntimeError):
            self.module["save_cache"](self.node)
        self.buttons["execute"].pressButton.assert_not_called()

    def test_constructed_mode_keeps_directory_guard(self):
        self.settings["filemethod"] = 0
        self.module["save_cache"](self.node)
        (self.root / "unrelated.txt").touch()
        with self.assertRaises(RuntimeError):
            self.module["save_background"](self.node)
        self.output.evalAtFrame.assert_not_called()

    def test_invalid_ranges_reject_before_saving(self):
        for setting in (
            {"f3": 0},
            {"f3": -1},
            {"substeps": 0},
            {"f2": 1000},
            {"f2": float("inf")},
            {"f3": float("nan")},
        ):
            with self.subTest(setting=setting):
                original = self.settings.copy()
                self.settings.update(setting)
                with self.assertRaises(RuntimeError):
                    self.module["save_cache"](self.node)
                self.settings.update(original)
        self.buttons["execute"].pressButton.assert_not_called()


if __name__ == "__main__":
    unittest.main()
