# -*- coding: utf-8 -*-
"""Pipeline tools for OpenPype Houdini integration."""
import os
import json
import logging

import hou  # noqa

from ayon_core.host import HostBase, IWorkfileHost, ILoadHost, IPublishHost
from ayon_core.tools.utils import host_tools
import pyblish.api

from ayon_core.pipeline import (
    register_creator_plugin_path,
    register_loader_plugin_path,
    register_inventory_action_path,
    register_workfile_build_plugin_path,
    AVALON_CONTAINER_ID,
    AYON_CONTAINER_ID,
)
from ayon_core.pipeline.load import any_outdated_containers
from ayon_houdini import HOUDINI_HOST_DIR
from ayon_houdini.api import lib, shelves, creator_node_shelves

from ayon_core.lib import (
    register_event_callback,
    emit_event,
    env_value_to_bool,
)

from .lib import JSON_PREFIX


log = logging.getLogger("ayon_houdini")

AVALON_CONTAINERS = "/obj/AVALON_CONTAINERS"
CONTEXT_CONTAINER = "/obj/OpenPypeContext"
IS_HEADLESS = not hasattr(hou, "ui")

PLUGINS_DIR = os.path.join(HOUDINI_HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")
WORKFILE_BUILD_PATH = os.path.join(PLUGINS_DIR, "workfile_build")

# Track whether the workfile tool is about to save
_about_to_save = False


class HoudiniHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
    name = "houdini"

    def __init__(self):
        super(HoudiniHost, self).__init__()
        self._op_events = {}
        self._has_been_setup = False

    def install(self):
        pyblish.api.register_host("houdini")
        pyblish.api.register_host("hython")
        pyblish.api.register_host("hpython")

        pyblish.api.register_plugin_path(PUBLISH_PATH)
        register_loader_plugin_path(LOAD_PATH)
        register_creator_plugin_path(CREATE_PATH)
        register_inventory_action_path(INVENTORY_PATH)
        register_workfile_build_plugin_path(WORKFILE_BUILD_PATH)

        log.info("Installing callbacks ... ")
        # register_event_callback("init", on_init)
        self._register_callbacks()
        register_event_callback("workfile.save.before", before_workfile_save)
        register_event_callback("before.save", before_save)
        register_event_callback("save", on_save)
        register_event_callback("open", on_open)
        register_event_callback("new", on_new)
        register_event_callback("taskChanged", on_task_changed)

        self._has_been_setup = True

        # Manually call on_new callback as it doesn't get called when AYON
        # launches for the first time on a context, only when going to
        # File -> New
        on_new()

        if not IS_HEADLESS:
            import hdefereval  # noqa, hdefereval is only available in ui mode
            # Defer generation of shelves due to issue on Windows where shelf
            # initialization during start up delays Houdini UI by minutes
            # making it extremely slow to launch.
            hdefereval.executeDeferred(shelves.generate_shelves)
            hdefereval.executeDeferred(creator_node_shelves.install)
            if env_value_to_bool("AYON_WORKFILE_TOOL_ON_START"):
                hdefereval.executeDeferred(
                    lambda: host_tools.show_workfiles(
                        parent=hou.qt.mainWindow()
                    )
                )

    def workfile_has_unsaved_changes(self):
        return hou.hipFile.hasUnsavedChanges()

    def get_workfile_extensions(self):
        return [".hip", ".hiplc", ".hipnc"]

    def save_workfile(self, dst_path=None):
        # Force forwards slashes to avoid segfault
        if dst_path:
            dst_path = dst_path.replace("\\", "/")
        hou.hipFile.save(file_name=dst_path,
                         save_to_recent_files=True)
        return dst_path

    def open_workfile(self, filepath):
        # Force forwards slashes to avoid segfault
        filepath = filepath.replace("\\", "/")

        try:
            hou.hipFile.load(filepath,
                             suppress_save_prompt=True,
                             ignore_load_warnings=False)
        except hou.LoadWarning as exc:
            log.warning(exc)

        return filepath

    def get_current_workfile(self):
        current_filepath = hou.hipFile.path()
        if (os.path.basename(current_filepath) == "untitled.hip" and
                not os.path.exists(current_filepath)):
            # By default a new scene in houdini is saved in the current
            # working directory as "untitled.hip" so we need to capture
            # that and consider it 'not saved' when it's in that state.
            return None

        return current_filepath

    def get_containers(self):
        return ls()

    def _register_callbacks(self):
        for event in self._op_events.copy().values():
            if event is None:
                continue

            try:
                hou.hipFile.removeEventCallback(event)
            except RuntimeError as e:
                log.info(e)

        self._op_events[on_file_event_callback] = hou.hipFile.addEventCallback(
            on_file_event_callback
        )

    @staticmethod
    def create_context_node():
        """Helper for creating context holding node.

        Returns:
            hou.Node: context node

        """
        obj_network = hou.node("/obj")
        op_ctx = obj_network.createNode("subnet",
                                        node_name="OpenPypeContext",
                                        run_init_scripts=False,
                                        load_contents=False)

        op_ctx.moveToGoodPosition()
        op_ctx.setBuiltExplicitly(False)
        op_ctx.setCreatorState("OpenPype")
        op_ctx.setComment("OpenPype node to hold context metadata")
        op_ctx.setColor(hou.Color((0.081, 0.798, 0.810)))
        op_ctx.setDisplayFlag(False)
        op_ctx.hide(True)
        return op_ctx

    def update_context_data(self, data, changes):
        op_ctx = hou.node(CONTEXT_CONTAINER)
        if not op_ctx:
            op_ctx = self.create_context_node()

        lib.imprint(op_ctx, data, update=True)

    def get_context_data(self):
        op_ctx = hou.node(CONTEXT_CONTAINER)
        if not op_ctx:
            op_ctx = self.create_context_node()
        return lib.read(op_ctx)

    def save_file(self, dst_path=None):
        # Force forwards slashes to avoid segfault
        dst_path = dst_path.replace("\\", "/")

        hou.hipFile.save(file_name=dst_path,
                         save_to_recent_files=True)


def on_file_event_callback(event):
    if event == hou.hipFileEventType.AfterLoad:
        emit_event("open")
    elif event == hou.hipFileEventType.AfterSave:
        emit_event("save")
    elif event == hou.hipFileEventType.BeforeSave:
        emit_event("before.save")
    elif event == hou.hipFileEventType.AfterClear:
        emit_event("new")


def containerise(name,
                 namespace,
                 nodes,
                 context,
                 loader=None,
                 suffix=""):
    """Bundle `nodes` into a subnet and imprint it with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        nodes (list): Long names of nodes to containerise
        context (dict): Asset information
        loader (str, optional): Name of loader used to produce this container.
        suffix (str, optional): Suffix of container, defaults to `_CON`.

    Returns:
        container (str): Name of container assembly

    """

    # Get AVALON_CONTAINERS subnet
    subnet = get_or_create_avalon_container()

    # Create proper container name
    container_name = "{}_{}".format(name, suffix or "CON")
    container = hou.node("/obj/{}".format(name))
    container.setName(container_name, unique_name=True)

    data = {
        "schema": "openpype:container-2.0",
        "id": AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace,
        "loader": str(loader),
        "representation": context["representation"]["id"],
        "project_name": context["project"]["name"]
    }

    lib.imprint(container, data)

    # "Parent" the container under the container network
    hou.moveNodesTo([container], subnet)

    subnet.node(container_name).moveToGoodPosition()

    return container


def parse_container(container):
    """Return the container node's full container data.

    Args:
        container (hou.Node): A container node name.

    Returns:
        dict: The container schema data for this container node.

    """
    # Read only relevant parms
    # TODO: Clean up this hack replacing `lib.read(container)`

    data = {}
    for name in ["name", "namespace", "loader", "representation", "id"]:
        parm = container.parm(name)
        if not parm:
            return {}

        value = parm.eval()

        # test if value is json encoded dict
        if isinstance(value, str) and value.startswith(JSON_PREFIX):
            try:
                value = json.loads(value[len(JSON_PREFIX):])
            except json.JSONDecodeError:
                # not a json
                pass
        data[name] = value

    # Support project name in container as optional attribute
    for name in ["project_name"]:
        parm = container.parm(name)
        if not parm:
            continue
        data[name] = parm.eval()

    # Backwards compatibility pre-schemas for containers
    data["schema"] = data.get("schema", "openpype:container-1.0")

    # Append transient data
    data["objectName"] = container.path()
    data["node"] = container

    return data


def ls():
    containers = []
    for identifier in (
        AYON_CONTAINER_ID,
        AVALON_CONTAINER_ID,
        "pyblish.mindbender.container"
    ):
        containers += lib.lsattr("id", identifier)

    for container in sorted(containers,
                            # Hou 19+ Python 3 hou.ObjNode are not
                            # sortable due to not supporting greater
                            # than comparisons
                            key=lambda node: node.path()):
        yield parse_container(container)


def before_workfile_save(event):
    global _about_to_save
    _about_to_save = True


def before_save():
    return lib.validate_fps()


def on_save():

    log.info("Running callback on save..")

    # update houdini vars
    lib.update_houdini_vars_context_dialog()

    # We are now starting the actual save directly
    global _about_to_save
    _about_to_save = False


def on_task_changed():
    global _about_to_save
    if not IS_HEADLESS and _about_to_save:
        # Let's prompt the user to update the context settings or not
        lib.prompt_reset_context()


def _show_outdated_content_popup():
    # Get main window
    parent = lib.get_main_window()
    if parent is None:
        log.info("Skipping outdated content pop-up "
                 "because Houdini window can't be found.")
        return

    from ayon_core.tools.utils import SimplePopup

    # Show outdated pop-up
    def _on_show_inventory():
        from ayon_core.tools.utils import host_tools
        host_tools.show_scene_inventory(parent=parent)

    dialog = SimplePopup(parent=parent)
    dialog.setWindowTitle("Houdini scene has outdated content")
    dialog.set_message("There are outdated containers in "
                      "your Houdini scene.")
    dialog.on_clicked.connect(_on_show_inventory)
    dialog.show()


def on_open():

    if not hou.isUIAvailable():
        log.debug("Batch mode detected, ignoring `on_open` callbacks..")
        return

    log.info("Running callback on open..")

    # update houdini vars
    lib.update_houdini_vars_context_dialog()

    # Validate FPS after update_task_from_path to
    # ensure it is using correct FPS for the folder
    lib.validate_fps()

    if any_outdated_containers():
        parent = lib.get_main_window()
        if parent is None:
            # When opening Houdini with last workfile on launch the UI hasn't
            # initialized yet completely when the `on_open` callback triggers.
            # We defer the dialog popup to wait for the UI to become available.
            # We assume it will open because `hou.isUIAvailable()` returns True
            import hdefereval
            hdefereval.executeDeferred(_show_outdated_content_popup)
        else:
            _show_outdated_content_popup()

        log.warning("Scene has outdated content.")


def on_new():
    """Set project resolution and fps when create a new file"""

    if hou.hipFile.isLoadingHipFile():
        # This event also triggers when Houdini opens a file due to the
        # new event being registered to 'afterClear'. As such we can skip
        # 'new' logic if the user is opening a file anyway
        log.debug("Skipping on new callback due to scene being opened.")
        return

    log.info("Running callback on new..")
    _set_context_settings()

    # It seems that the current frame always gets reset to frame 1 on
    # new scene. So we enforce current frame to be at the start of the playbar
    # with execute deferred
    def _enforce_start_frame():
        start = hou.playbar.playbackRange()[0]
        hou.setFrame(start)

    if hou.isUIAvailable():
        import hdefereval
        hdefereval.executeDeferred(lib.start_workfile_template_builder)
        hdefereval.executeDeferred(_enforce_start_frame)
    else:
        # Run without execute deferred when no UI is available because
        # without UI `hdefereval` is not available to import
        _enforce_start_frame()


def get_or_create_avalon_container() -> "hou.OpNode":
    avalon_container = hou.node(AVALON_CONTAINERS)
    if avalon_container:
        return avalon_container

    parent_path, name = AVALON_CONTAINERS.rsplit("/", 1)
    parent = hou.node(parent_path)
    return parent.createNode(
        "subnet", node_name=name
    )


def _set_context_settings():
    """Apply the project settings from the project definition

    Settings can be overwritten by a folder if the folder.attrib contains
    any information regarding those settings.

    Examples of settings:
        fps
        resolution
        renderer

    Returns:
        None
    """

    lib.reset_framerange()
    lib.update_houdini_vars_context()
