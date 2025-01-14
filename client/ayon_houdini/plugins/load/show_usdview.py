import os
import platform
import subprocess

from ayon_core.lib.vendor_bin_utils import find_executable
from ayon_houdini.api import plugin


class ShowInUsdview(plugin.HoudiniLoader):
    """Open USD file in usdview"""

    label = "Show in usdview"
    representations = {"*"}
    product_types = {"*"}
    extensions = {"usd", "usda", "usdlc", "usdnc", "abc"}
    order = 15

    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        from pathlib import Path

        if platform.system() == "Windows":
            houdiniVersion = os.environ["HOUDINI_VERSION"]
            major = int(houdiniVersion.split(".")[0])
            if major >= 20:
                executable = "usdview.cmd"
            else:
                executable = "usdview.bat"
        else:
            executable = "usdview"

        usdview = find_executable(executable)
        if not usdview:
            raise RuntimeError("Unable to find usdview")

        # For some reason Windows can return the path like:
        # C:/PROGRA~1/SIDEEF~1/HOUDIN~1.435/bin/usdview
        # convert to resolved path so `subprocess` can take it
        usdview = str(Path(usdview).resolve().as_posix())

        filepath = self.filepath_from_context(context)
        filepath = os.path.normpath(filepath)
        filepath = filepath.replace("\\", "/")

        if not os.path.exists(filepath):
            self.log.error("File does not exist: %s" % filepath)
            return

        self.log.info("Start houdini variant of usdview...")

        subprocess.Popen([usdview, filepath, "--renderer", "GL"])
