import os
from ayon_core.addon import AYONAddon, IHostAddon

from .version import __version__

HOUDINI_HOST_DIR = os.path.dirname(os.path.abspath(__file__))


class HoudiniAddon(AYONAddon, IHostAddon):
    name = "houdini"
    version = __version__
    host_name = "houdini"

    def add_implementation_envs(self, env, _app):
        # Add requirements to HOUDINI_PATH
        startup_path = os.path.join(HOUDINI_HOST_DIR, "startup")
        new_houdini_path = [startup_path]

        old_houdini_path = env.get("HOUDINI_PATH") or ""
        for path in old_houdini_path.split(os.pathsep):
            if not path:
                continue

            norm_path = os.path.normpath(path)
            if norm_path not in new_houdini_path:
                new_houdini_path.append(norm_path)

        # Add & (ampersand), it represents "the standard Houdini Path contents"
        new_houdini_path.append("&")
        env["HOUDINI_PATH"] = os.pathsep.join(new_houdini_path)

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(HOUDINI_HOST_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".hip", ".hiplc", ".hipnc"]
