# -*- coding: utf-8 -*-
import sys
import os
import errno
import re
import logging
import json
from contextlib import contextmanager

import six
import ayon_api

import hou

from ayon_core.lib import StringTemplate
from ayon_core.settings import get_current_project_settings
from ayon_core.pipeline import (
    Anatomy,
    registered_host,
    get_current_context,
    get_current_host_name,
)
from ayon_core.pipeline.create import CreateContext
from ayon_core.pipeline.template_data import get_template_data
from ayon_core.pipeline.context_tools import get_current_task_entity
from ayon_core.pipeline.workfile.workfile_template_builder import (
    TemplateProfileNotFound
)
from ayon_core.tools.utils import PopupUpdateKeys, SimplePopup
from ayon_core.tools.utils.host_tools import get_tool_by_name


self = sys.modules[__name__]
self._parent = None
log = logging.getLogger(__name__)
JSON_PREFIX = "JSON:::"


def get_entity_fps(entity=None):
    """Return current task fps or fps from an entity."""

    if entity is None:
        entity = get_current_task_entity(fields=["attrib.fps"])
    return entity["attrib"]["fps"]


def get_output_parameter(node):
    """Return the render output parameter of the given node

    Example:
        root = hou.node("/obj")
        my_alembic_node = root.createNode("alembic")
        get_output_parameter(my_alembic_node)
        >>> "filename"

    Notes:
        I'm using node.type().name() to get on par with the creators,
            Because the return value of `node.type().name()` is the
            same string value used in creators
            e.g. instance_data.update({"node_type": "alembic"})

        Rop nodes in different network categories have
            the same output parameter.
            So, I took that into consideration as a hint for
            future development.

    Args:
        node(hou.Node): node instance

    Returns:
        hou.Parm
    """

    node_type = node.type().name()

    # Figure out which type of node is being rendered
    if node_type in {"alembic", "rop_alembic"}:
        return node.parm("filename")
    elif node_type == "arnold":
        if node_type.evalParm("ar_ass_export_enable"):
            return node.parm("ar_ass_file")
        return node.parm("ar_picture")
    elif node_type in {
        "geometry",
        "rop_geometry",
        "filmboxfbx",
        "rop_fbx"
    }:
        return node.parm("sopoutput")
    elif node_type == "comp":
        return node.parm("copoutput")
    elif node_type in {"karma", "opengl"}:
        return node.parm("picture")
    elif node_type == "ifd":  # Mantra
        if node.evalParm("soho_outputmode"):
            return node.parm("soho_diskfile")
        return node.parm("vm_picture")
    elif node_type == "Redshift_Proxy_Output":
        return node.parm("RS_archive_file")
    elif node_type == "Redshift_ROP":
        return node.parm("RS_outputFileNamePrefix")
    elif node_type in {"usd", "usd_rop", "usdexport"}:
        return node.parm("lopoutput")
    elif node_type in {"usdrender", "usdrender_rop"}:
        return node.parm("outputimage")
    elif node_type == "vray_renderer":
        return node.parm("SettingsOutput_img_file_path")

    raise TypeError("Node type '%s' not supported" % node_type)


def get_lops_rop_context_options(
        ropnode: hou.RopNode) -> "dict[str, str | float]":
    """Return the Context Options that a LOP ROP node uses."""
    rop_context_options: "dict[str, str | float]" = {}

    # Always set @ropname and @roppath
    # See: https://www.sidefx.com/docs/houdini/hom/hou/isAutoContextOption.html
    rop_context_options["ropname"] = ropnode.name()
    rop_context_options["roppath"] = ropnode.path()

    # Set @ropcook, @ropstart, @ropend and @ropinc if setropcook is enabled
    setropcook_parm = ropnode.parm("setropcook")
    if setropcook_parm:
        setropcook = setropcook_parm.eval()
        if setropcook:
            # TODO: Support "Render Frame Range from Stage" correctly
            # TODO: Support passing in the start, end, and increment values
            #  for the cases where this may need to consider overridden
            #  frame ranges for `RopNode.render()` calls.
            trange = ropnode.evalParm("trange")
            if trange == 0:
                # Current frame
                start: float = hou.frame()
                end: float = start
                inc: float = 1.0
            elif trange in {1, 2}:
                # Frame range
                start: float = ropnode.evalParm("f1")
                end: float = ropnode.evalParm("f2")
                inc: float = ropnode.evalParm("f3")
            else:
                raise ValueError("Unsupported trange value: %s" % trange)
            rop_context_options["ropcook"] = 1.0
            rop_context_options["ropstart"] = start
            rop_context_options["ropend"] = end
            rop_context_options["ropinc"] = inc

    # Get explicit context options set on the ROP node.
    num = ropnode.evalParm("optioncount")
    for i in range(1, num + 1):
        # Ignore disabled options
        if not ropnode.evalParm(f"optionenable{i}"):
            continue

        name: str = ropnode.evalParm(f"optionname{i}")
        option_type: str = ropnode.evalParm(f"optiontype{i}")
        if option_type == "string":
            value: str = ropnode.evalParm(f"optionstrvalue{i}")
        elif option_type == "float":
            value: float = ropnode.evalParm(f"optionfloatvalue{i}")
        else:
            raise ValueError(f"Unsupported option type: {option_type}")
        rop_context_options[name] = value

    return rop_context_options


@contextmanager
def context_options(context_options: "dict[str, str | float]"):
    """Context manager to set Solaris Context Options.

    The original context options are restored after the context exits.

    Arguments:
        context_options (dict[str, str | float]):
            The Solaris Context Options to set.

    Yields:
        dict[str, str | float]: The original context options that were changed.

    """
    # Get the original context options and their values
    original_context_options: "dict[str, str | float]" = {}
    for name in hou.contextOptionNames():
        original_context_options[name] = hou.contextOption(name)

    try:
        # Override the context options
        for name, value in context_options.items():
            hou.setContextOption(name, value)
        yield original_context_options
    finally:
        # Restore original context options that we changed
        for name in context_options:
            if name in original_context_options:
                hou.setContextOption(name, original_context_options[name])
            else:
                # Clear context option
                hou.setContextOption(name, None)


@contextmanager
def update_mode_context(mode):
    original = hou.updateModeSetting()
    try:
        hou.setUpdateMode(mode)
        yield
    finally:
        hou.setUpdateMode(original)


def set_scene_fps(fps):
    hou.setFps(fps)


# Valid FPS
def validate_fps():
    """Validate current scene FPS and show pop-up when it is incorrect

    Returns:
        bool

    """

    fps = get_entity_fps()
    current_fps = hou.fps()  # returns float

    if current_fps != fps:

        # Find main window
        parent = hou.ui.mainQtWindow()
        if parent is None:
            pass
        else:
            dialog = PopupUpdateKeys(parent=parent)
            dialog.setModal(True)
            dialog.setWindowTitle("Houdini scene does not match project FPS")
            dialog.set_message("Scene %i FPS does not match project %i FPS" %
                              (current_fps, fps))
            dialog.set_button_text("Fix")

            # on_show is the Fix button clicked callback
            dialog.on_clicked_state.connect(lambda: set_scene_fps(fps))

            dialog.show()

            return False

    return True


def render_rop(ropnode, frame_range=None):
    """Render ROP node utility for Publishing.

    This renders a ROP node with the settings we want during Publishing.

    Args:
        ropnode (hou.RopNode): Node to render
        frame_range (tuple): Copied from Houdini's help..
            Sequence of 2 or 3 values, overrides the frame range and frame
            increment to render. The first two values specify the start and
            end frames, and the third value (if given) specifies the frame
            increment. If no frame increment is given and the ROP node
            doesn't specify a frame increment, then a value of 1 will be
            used. If no frame range is given, and the ROP node doesn't
            specify a frame range, then the current frame will be rendered.
    """

    if frame_range is None:
        frame_range = ()

    # Print verbose when in batch mode without UI
    verbose = not hou.isUIAvailable()

    # Render
    try:
        ropnode.render(verbose=verbose,
                       # Allow Deadline to capture completion percentage
                       output_progress=verbose,
                       # Render only this node
                       # (do not render any of its dependencies)
                       ignore_inputs=True,
                       frame_range=frame_range)
    except hou.Error as exc:
        # The hou.Error is not inherited from a Python Exception class,
        # so we explicitly capture the houdini error, otherwise pyblish
        # will remain hanging.
        import traceback
        traceback.print_exc()
        raise RuntimeError("Render failed: {0}".format(exc))


def imprint(node, data, update=False):
    """Store attributes with value on a node

    Depending on the type of attribute it creates the correct parameter
    template. Houdini uses a template per type, see the docs for more
    information.

    http://www.sidefx.com/docs/houdini/hom/hou/ParmTemplate.html

    Because of some update glitch where you cannot overwrite existing
    ParmTemplates on node using:
        `setParmTemplates()` and `parmTuplesInFolder()`
    update is done in another pass.

    Args:
        node(hou.Node): node object from Houdini
        data(dict): collection of attributes and their value
        update (bool, optional): flag if imprint should update
            already existing data or leave them untouched and only
            add new.

    Returns:
        None

    """
    if not data:
        return
    if not node:
        self.log.error("Node is not set, calling imprint on invalid data.")
        return

    current_parms = {p.name(): p for p in node.spareParms()}
    update_parm_templates = []
    new_parm_templates = []

    for key, value in data.items():
        if value is None:
            continue

        parm_template = get_template_from_value(key, value)

        if key in current_parms:
            if node.evalParm(key) == value:
                continue
            if not update:
                log.debug(f"{key} already exists on {node}")
            else:
                log.debug(f"replacing {key}")
                update_parm_templates.append(parm_template)
            continue

        new_parm_templates.append(parm_template)

    if not new_parm_templates and not update_parm_templates:
        return

    parm_group = node.parmTemplateGroup()

    # Add new parm templates
    if new_parm_templates:
        parm_folder = parm_group.findFolder("Extra")

        # if folder doesn't exist yet, create one and append to it,
        # else append to existing one
        if not parm_folder:
            parm_folder = hou.FolderParmTemplate("folder", "Extra")
            parm_folder.setParmTemplates(new_parm_templates)
            parm_group.append(parm_folder)
        else:
            # Add to parm template folder instance then replace with updated
            # one in parm template group
            for template in new_parm_templates:
                parm_folder.addParmTemplate(template)
            parm_group.replace(parm_folder.name(), parm_folder)

    # Update existing parm templates
    for parm_template in update_parm_templates:
        parm_group.replace(parm_template.name(), parm_template)

        # When replacing a parm with a parm of the same name it preserves its
        # value if before the replacement the parm was not at the default,
        # because it has a value override set. Since we're trying to update the
        # parm by using the new value as `default` we enforce the parm is at
        # default state
        node.parm(parm_template.name()).revertToDefaults()

    node.setParmTemplateGroup(parm_group)


def lsattr(attr, value=None, root="/"):
    """Return nodes that have `attr`
     When `value` is not None it will only return nodes matching that value
     for the given attribute.
     Args:
         attr (str): Name of the attribute (hou.Parm)
         value (object, Optional): The value to compare the attribute too.
            When the default None is provided the value check is skipped.
        root (str): The root path in Houdini to search in.
    Returns:
        list: Matching nodes that have attribute with value.
    """
    if value is None:
        # Use allSubChildren() as allNodes() errors on nodes without
        # permission to enter without a means to continue of querying
        # the rest
        nodes = hou.node(root).allSubChildren()
        return [n for n in nodes if n.parm(attr)]
    return lsattrs({attr: value})


def lsattrs(attrs, root="/"):
    """Return nodes matching `key` and `value`
    Arguments:
        attrs (dict): collection of attribute: value
        root (str): The root path in Houdini to search in.
    Example:
        >> lsattrs({"id": "myId"})
        ["myNode"]
        >> lsattr("id")
        ["myNode", "myOtherNode"]
    Returns:
        list: Matching nodes that have attribute with value.
    """

    matches = set()
    # Use allSubChildren() as allNodes() errors on nodes without
    # permission to enter without a means to continue of querying
    # the rest
    nodes = hou.node(root).allSubChildren()
    for node in nodes:
        for attr in attrs:
            if not node.parm(attr):
                continue
            elif node.evalParm(attr) != attrs[attr]:
                continue
            else:
                matches.add(node)

    return list(matches)


def read(node):
    """Read the container data in to a dict

    Args:
        node(hou.Node): Houdini node

    Returns:
        dict

    """
    # `spareParms` returns a tuple of hou.Parm objects
    data = {}
    if not node:
        return data
    for parameter in node.spareParms():
        value = parameter.eval()
        # test if value is json encoded dict
        if isinstance(value, six.string_types) and \
                value.startswith(JSON_PREFIX):
            try:
                value = json.loads(value[len(JSON_PREFIX):])
            except json.JSONDecodeError:
                # not a json
                pass
        data[parameter.name()] = value

    return data


@contextmanager
def maintained_selection():
    """Maintain selection during context
    Example:
        >>> with maintained_selection():
        ...     # Modify selection
        ...     node.setSelected(on=False, clear_all_selected=True)
        >>> # Selection restored
    """

    previous_selection = hou.selectedNodes()
    try:
        yield
    finally:
        # Clear the selection
        # todo: does hou.clearAllSelected() do the same?
        for node in hou.selectedNodes():
            node.setSelected(on=False)

        if previous_selection:
            for node in previous_selection:
                node.setSelected(on=True)


@contextmanager
def parm_values(overrides):
    """Override Parameter values during the context.
    Arguments:
        overrides (List[Tuple[hou.Parm, Any]]): The overrides per parm
            that should be applied during context.
    """

    originals = []
    try:
        for parm, value in overrides:
            originals.append((parm, parm.eval()))
            parm.set(value)
        yield
    finally:
        for parm, value in originals:
            # Parameter might not exist anymore so first
            # check whether it's still valid
            if hou.parm(parm.path()):
                parm.set(value)


def reset_framerange(fps=True, frame_range=True):
    """Set frame range and FPS to current folder."""

    task_entity = get_current_task_entity(fields={"attrib"})

    # Set FPS
    if fps:
        fps = get_entity_fps(task_entity)
        print("Setting scene FPS to {}".format(int(fps)))
        set_scene_fps(fps)

    if frame_range:

        # Set Start and End Frames
        task_attrib = task_entity["attrib"]
        frame_start = task_attrib.get("frameStart", 0)
        frame_end = task_attrib.get("frameEnd", 0)

        handle_start = task_attrib.get("handleStart", 0)
        handle_end = task_attrib.get("handleEnd", 0)

        frame_start -= int(handle_start)
        frame_end += int(handle_end)

        # Set frame range and FPS
        hou.playbar.setFrameRange(frame_start, frame_end)
        hou.playbar.setPlaybackRange(frame_start, frame_end)
        hou.setFrame(frame_start)


def get_main_window():
    """Acquire Houdini's main window"""
    if self._parent is None:
        self._parent = hou.ui.mainQtWindow()
    return self._parent


def get_template_from_value(key, value):
    if isinstance(value, float):
        parm = hou.FloatParmTemplate(name=key,
                                     label=key,
                                     num_components=1,
                                     default_value=(value,))
    elif isinstance(value, bool):
        parm = hou.ToggleParmTemplate(name=key,
                                      label=key,
                                      default_value=value)
    elif isinstance(value, int):
        parm = hou.IntParmTemplate(name=key,
                                   label=key,
                                   num_components=1,
                                   default_value=(value,))
    elif isinstance(value, six.string_types):
        parm = hou.StringParmTemplate(name=key,
                                      label=key,
                                      num_components=1,
                                      default_value=(value,))
    elif isinstance(value, (dict, list, tuple)):
        parm = hou.StringParmTemplate(name=key,
                                      label=key,
                                      num_components=1,
                                      default_value=(
                                          JSON_PREFIX + json.dumps(value),))
    else:
        raise TypeError("Unsupported type: %r" % type(value))

    return parm


def get_frame_data(node, log=None):
    """Get the frame data: `frameStartHandle`, `frameEndHandle`
    and `byFrameStep`.

    This function uses Houdini node's `trange`, `t1, `t2` and `t3`
    parameters as the source of truth for the full inclusive frame
    range to render, as such these are considered as the frame
    range including the handles.

    The non-inclusive frame start and frame end without handles
    can be computed by subtracting the handles from the inclusive
    frame range.

    Args:
        node (hou.Node): ROP node to retrieve frame range from,
            the frame range is assumed to be the frame range
            *including* the start and end handles.

    Returns:
        dict: frame data for `frameStartHandle`, `frameEndHandle`
            and `byFrameStep`.

    """

    if log is None:
        log = self.log

    data = {}

    if node.parm("trange") is None:
        log.debug(
            "Node has no 'trange' parameter: {}".format(node.path())
        )
        return data

    if node.evalParm("trange") == 0:
        data["frameStartHandle"] = hou.intFrame()
        data["frameEndHandle"] = hou.intFrame()
        data["byFrameStep"] = 1.0

        log.info(
            "Node '{}' has 'Render current frame' set.\n"
            "Task handles are ignored.\n"
            "frameStart and frameEnd are set to the "
            "current frame.".format(node.path())
        )
    else:
        data["frameStartHandle"] = int(node.evalParm("f1"))
        data["frameEndHandle"] = int(node.evalParm("f2"))
        data["byFrameStep"] = node.evalParm("f3")

    return data


def splitext(name, allowed_multidot_extensions):
    # type: (str, list) -> tuple
    """Split file name to name and extension.

    Args:
        name (str): File name to split.
        allowed_multidot_extensions (list of str): List of allowed multidot
            extensions.

    Returns:
        tuple: Name and extension.
    """

    for ext in allowed_multidot_extensions:
        if name.endswith(ext):
            return name[:-len(ext)], ext

    return os.path.splitext(name)


def get_top_referenced_parm(parm):

    processed = set()  # disallow infinite loop
    while True:
        if parm.path() in processed:
            raise RuntimeError("Parameter references result in cycle.")

        processed.add(parm.path())

        ref = parm.getReferencedParm()
        if ref.path() == parm.path():
            # It returns itself when it doesn't reference
            # another parameter
            return ref
        else:
            parm = ref


def evalParmNoFrame(node, parm, pad_character="#"):

    parameter = node.parm(parm)
    assert parameter, "Parameter does not exist: %s.%s" % (node, parm)

    # If the parameter has a parameter reference, then get that
    # parameter instead as otherwise `unexpandedString()` fails.
    parameter = get_top_referenced_parm(parameter)

    # Substitute out the frame numbering with padded characters
    try:
        raw = parameter.unexpandedString()
    except hou.Error as exc:
        print("Failed: %s" % parameter)
        raise RuntimeError(exc)

    def replace(match):
        padding = 1
        n = match.group(2)
        if n and int(n):
            padding = int(n)
        return pad_character * padding

    expression = re.sub(r"(\$F([0-9]*))", replace, raw)

    with hou.ScriptEvalContext(parameter):
        return hou.expandStringAtFrame(expression, 0)


def get_color_management_preferences():
    """Get default OCIO preferences"""

    preferences = {
        "config": hou.Color.ocio_configPath(),
        "display": hou.Color.ocio_defaultDisplay(),
        "view": hou.Color.ocio_defaultView()
    }

    # Note: For whatever reason they are cases where `view` may be an empty
    #  string even though a valid default display is set where `PyOpenColorIO`
    #  does correctly return the values.
    # Workaround to get the correct default view
    if preferences["config"] and not preferences["view"]:
        log.debug(
            "Houdini `hou.Color.ocio_defaultView()` returned empty value."
            " Falling back to `PyOpenColorIO` to get the default view.")
        try:
            import PyOpenColorIO
        except ImportError:
            log.warning(
                "Unable to workaround empty return value of "
                "`hou.Color.ocio_defaultView()` because `PyOpenColorIO` is "
                "not available.")
            return preferences

        config_path = preferences["config"]
        config = PyOpenColorIO.Config.CreateFromFile(config_path)
        display = config.getDefaultDisplay()
        assert display == preferences["display"], \
            "Houdini default OCIO display must match config default display"
        view = config.getDefaultView(display)
        preferences["display"] = display
        preferences["view"] = view

    return preferences


def get_obj_node_output(obj_node):
    """Find output node.

    If the node has any output node return the
    output node with the minimum `outputidx`.
    When no output is present return the node
    with the display flag set. If no output node is
    detected then None is returned.

    Arguments:
        node (hou.Node): The node to retrieve a single
            the output node for.

    Returns:
        Optional[hou.Node]: The child output node.

    """

    outputs = obj_node.subnetOutputs()
    if not outputs:
        return

    elif len(outputs) == 1:
        return outputs[0]

    else:
        return min(outputs,
                   key=lambda node: node.evalParm('outputidx'))


def get_output_children(output_node, include_sops=True):
    """Recursively return a list of all output nodes
    contained in this node including this node.

    It works in a similar manner to output_node.allNodes().
    """
    out_list = [output_node]

    if output_node.childTypeCategory() == hou.objNodeTypeCategory():
        for child in output_node.children():
            out_list += get_output_children(child, include_sops=include_sops)

    elif include_sops and \
            output_node.childTypeCategory() == hou.sopNodeTypeCategory():
        out = get_obj_node_output(output_node)
        if out:
            out_list += [out]

    return out_list


def get_resolution_from_entity(entity):
    """Get resolution from the given entity.

    Args:
        entity (dict[str, Any]): Project, Folder or Task entity.

    Returns:
        Union[Tuple[int, int], None]: Resolution width and height.

    """
    if not entity or "attrib" not in entity:
        raise ValueError(f"Entity is not valid: \"{entity}\"")

    attributes = entity["attrib"]
    resolution_width = attributes.get("resolutionWidth")
    resolution_height = attributes.get("resolutionHeight")

    # Make sure both width and height are set
    if resolution_width is None or resolution_height is None:
        print(f"No resolution information found in entity: '{entity}'")
        return None

    return int(resolution_width), int(resolution_height)


def set_camera_resolution(camera, entity=None):
    """Apply resolution to camera from task or folder entity.

    Arguments:
        camera (hou.OpNode): Camera node.
        entity (Optional[Dict[str, Any]]): Folder or task entity.
            If not provided falls back to current task entity.
    """

    if not entity:
        entity = get_current_task_entity()

    resolution = get_resolution_from_entity(entity)

    if resolution:
        print("Setting camera resolution: {} -> {}x{}".format(
            camera.name(), resolution[0], resolution[1]
        ))
        camera.parm("resx").set(resolution[0])
        camera.parm("resy").set(resolution[1])


def get_camera_from_container(container):
    """Get camera from container node. """

    cameras = container.recursiveGlob(
        "*",
        filter=hou.nodeTypeFilter.ObjCamera,
        include_subnets=False
    )

    assert len(cameras) == 1, "Camera instance must have only one camera"
    return cameras[0]


def get_current_context_template_data_with_entity_attrs():
    """Return template data including current context folder and task attribs.

    Output contains:
      - Regular template data from `get_template_data`
      - 'folderAttributes' key with folder attribute values.
      - 'taskAttributes' key with task attribute values.

    Returns:
         dict[str, Any]: Template data to fill templates.

    """
    context = get_current_context()
    project_name = context["project_name"]
    folder_path = context["folder_path"]
    task_name = context["task_name"]
    host_name = get_current_host_name()

    project_entity = ayon_api.get_project(project_name)
    anatomy = Anatomy(project_name, project_entity=project_entity)
    folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
    task_entity = ayon_api.get_task_by_name(
        project_name, folder_entity["id"], task_name
    )

    # get context specific vars
    folder_attributes = folder_entity["attrib"]
    task_attributes = task_entity["attrib"]

    # compute `frameStartHandle` and `frameEndHandle`
    for attributes in [folder_attributes, task_attributes]:
        frame_start = attributes.get("frameStart")
        frame_end = attributes.get("frameEnd")
        handle_start = attributes.get("handleStart")
        handle_end = attributes.get("handleEnd")
        if frame_start is not None and handle_start is not None:
            attributes["frameStartHandle"] = frame_start - handle_start
        if frame_end is not None and handle_end is not None:
            attributes["frameEndHandle"] = frame_end + handle_end

    template_data = get_template_data(
        project_entity, folder_entity, task_entity, host_name
    )
    template_data["root"] = anatomy.roots
    template_data["folderAttributes"] = folder_attributes
    template_data["taskAttributes"] = task_attributes

    return template_data


def set_review_color_space(opengl_node, review_color_space="", log=None):
    """Set ociocolorspace parameter for the given OpenGL node.

    Set `ociocolorspace` parameter of the given OpenGl node
    to to the given review_color_space value.
    If review_color_space is empty, a default colorspace corresponding to
    the display & view of the current Houdini session will be used.

    Args:
        opengl_node (hou.Node): ROP node to set its ociocolorspace parm.
        review_color_space (str): Colorspace value for ociocolorspace parm.
        log (logging.Logger): Logger to log to.
    """

    if log is None:
        log = self.log

    # Set Color Correction parameter to OpenColorIO
    colorcorrect_parm = opengl_node.parm("colorcorrect")
    if colorcorrect_parm.eval() != 2:
        colorcorrect_parm.set(2)
        log.debug(
            "'Color Correction' parm on '{}' has been set to"
            " 'OpenColorIO'".format(opengl_node.path())
        )

    opengl_node.setParms(
        {"ociocolorspace": review_color_space}
    )

    log.debug(
        "'OCIO Colorspace' parm on '{}' has been set to "
        "the view color space '{}'"
        .format(opengl_node, review_color_space)
    )


def get_context_var_changes():
    """get context var changes."""

    houdini_vars_to_update = {}

    project_settings = get_current_project_settings()
    houdini_vars_settings = \
        project_settings["houdini"]["general"]["update_houdini_var_context"]

    if not houdini_vars_settings["enabled"]:
        return houdini_vars_to_update

    houdini_vars = houdini_vars_settings["houdini_vars"]

    # No vars specified - nothing to do
    if not houdini_vars:
        return houdini_vars_to_update

    # Get Template data
    template_data = get_current_context_template_data_with_entity_attrs()

    # Set Houdini Vars
    for item in houdini_vars:
        # For consistency reasons we always force all vars to be uppercase
        # Also remove any leading, and trailing whitespaces.
        var = item["var"].strip().upper()

        # get and resolve template in value
        item_value = StringTemplate.format_template(
            item["value"],
            template_data
        )

        if var == "JOB" and item_value == "":
            # sync $JOB to $HIP if $JOB is empty
            item_value = os.environ["HIP"]

        if item["is_directory"]:
            item_value = item_value.replace("\\", "/")

        current_value = hou.hscript("echo -n `${}`".format(var))[0]

        if current_value != item_value:
            houdini_vars_to_update[var] = (
                current_value, item_value, item["is_directory"]
            )

    return houdini_vars_to_update


def update_houdini_vars_context():
    """Update task context variables"""

    for var, (_old, new, is_directory) in get_context_var_changes().items():
        if is_directory:
            try:
                os.makedirs(new)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    print(
                        "Failed to create ${} dir. Maybe due to "
                        "insufficient permissions.".format(var)
                    )

        hou.hscript("set {}={}".format(var, new))
        os.environ[var] = new
        print("Updated ${} to {}".format(var, new))


def update_houdini_vars_context_dialog():
    """Show pop-up to update task context variables"""
    update_vars = get_context_var_changes()
    if not update_vars:
        # Nothing to change
        print("Nothing to change, Houdini vars are already up to date.")
        return

    message = "\n".join(
        "${}: {} -> {}".format(var, old or "None", new or "None")
        for var, (old, new, _is_directory) in update_vars.items()
    )

    # TODO: Use better UI!
    parent = hou.ui.mainQtWindow()
    dialog = SimplePopup(parent=parent)
    dialog.setModal(True)
    dialog.setWindowTitle("Houdini scene has outdated task variables")
    dialog.set_message(message)
    dialog.set_button_text("Fix")

    # on_show is the Fix button clicked callback
    dialog.on_clicked.connect(update_houdini_vars_context)

    dialog.show()


def publisher_show_and_publish(comment=None):
    """Open publisher window and trigger publishing action.

    Args:
        comment (Optional[str]): Comment to set in publisher window.
    """

    main_window = get_main_window()
    publisher_window = get_tool_by_name(
        tool_name="publisher",
        parent=main_window,
    )
    publisher_window.show_and_publish(comment)


def find_rop_input_dependencies(input_tuple):
    """Self publish from ROP nodes.

    Arguments:
        tuple (hou.RopNode.inputDependencies) which can be a nested tuples
        represents the input dependencies of the ROP node, consisting of ROPs,
        and the frames that need to be be rendered prior to rendering the ROP.

    Returns:
        list of the RopNode.path() that can be found inside
        the input tuple.
    """

    out_list = []
    if isinstance(input_tuple[0], hou.RopNode):
        return input_tuple[0].path()

    if isinstance(input_tuple[0], tuple):
        for item in input_tuple:
            out_list.append(find_rop_input_dependencies(item))

    return out_list


def self_publish():
    """Self publish from ROP nodes.

    Firstly, it gets the node and its dependencies.
    Then, it deactivates all other ROPs
    And finally, it triggers the publishing action.
    """

    result, comment = hou.ui.readInput(
        "Add Publish Comment",
        buttons=("Publish", "Cancel"),
        title="Publish comment",
        close_choice=1
    )

    if result:
        return

    current_node = hou.node(".")
    inputs_paths = find_rop_input_dependencies(
        current_node.inputDependencies()
    )
    inputs_paths.append(current_node.path())

    host = registered_host()
    context = CreateContext(host, reset=True)

    for instance in context.instances:
        node_path = instance.data.get("instance_node")
        instance["active"] = node_path and node_path in inputs_paths

    context.save_changes()

    publisher_show_and_publish(comment)


def add_self_publish_button(node):
    """Adds a self publish button to the rop node."""

    label = os.environ.get("AYON_MENU_LABEL") or "AYON"

    button_parm = hou.ButtonParmTemplate(
        "ayon_self_publish",
        "{} Publish".format(label),
        script_callback="from ayon_houdini.api.lib import "
                        "self_publish; self_publish()",
        script_callback_language=hou.scriptLanguage.Python,
        join_with_next=True
    )

    template = node.parmTemplateGroup()
    template.insertBefore((0,), button_parm)
    node.setParmTemplateGroup(template)


def get_scene_viewer(visible_only=True):
    """
    Return an instance of a visible viewport.

    There may be many, some could be closed, any visible are current

    Arguments:
        visible_only (Optional[bool]): Only return viewers that currently
            are the active tab (and hence are visible).

    Returns:
        Optional[hou.SceneViewer]: A scene viewer, if any.
    """
    panes = hou.ui.paneTabs()
    panes = [x for x in panes if x.type() == hou.paneTabType.SceneViewer]

    if visible_only:
        return next((pane for pane in panes if pane.isCurrentTab()), None)

    panes = sorted(panes, key=lambda x: x.isCurrentTab())
    if panes:
        return panes[-1]

    return None


def sceneview_snapshot(
        sceneview,
        filepath="$HIP/thumbnails/$HIPNAME.$F4.jpg",
        frame_start=None,
        frame_end=None):
    """Take a snapshot of your scene view.

    It takes snapshot of your scene view for the given frame range.
    So, it's capable of generating snapshots image sequence.
    It works in different Houdini context e.g. Objects, Solaris

    Example::
        >>> from ayon_houdini.api import lib
        >>> sceneview = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        >>> lib.sceneview_snapshot(sceneview)

    Notes:
        .png output will render poorly, so use .jpg.

        How it works:
            Get the current sceneviewer (may be more than one or hidden)
            and screengrab the perspective viewport to a file in the
            publish location to be picked up with the publish.

        Credits:
            https://www.sidefx.com/forum/topic/42808/?page=1#post-354796

    Args:
        sceneview (hou.SceneViewer): The scene view pane from which you want
                                     to take a snapshot.
        filepath (str): thumbnail filepath. it expects `$F4` token
                        when frame_end is bigger than frame_star other wise
                        each frame will override its predecessor.
        frame_start (int): the frame at which snapshot starts
        frame_end (int): the frame at which snapshot ends
    """

    if frame_start is None:
        frame_start = hou.frame()
    if frame_end is None:
        frame_end = frame_start

    if not isinstance(sceneview, hou.SceneViewer):
        log.debug("Wrong Input. {} is not of type hou.SceneViewer."
                  .format(sceneview))
        return
    viewport = sceneview.curViewport()

    flip_settings = sceneview.flipbookSettings().stash()
    flip_settings.frameRange((frame_start, frame_end))
    flip_settings.output(filepath)
    flip_settings.outputToMPlay(False)
    sceneview.flipbook(viewport, flip_settings)
    log.debug("A snapshot of sceneview has been saved to: {}".format(filepath))


def get_background_images(node, raw=False):
    """"Return background images defined inside node.

    Similar to `nodegraphutils.saveBackgroundImages` but this method also
    allows to retrieve the data as JSON encodable data instead of
    `hou.NetworkImage` instances when using `raw=True`
    """

    def _parse(image_data):
        image = hou.NetworkImage(image_data["path"],
                                 hou.BoundingRect(*image_data["rect"]))
        if "relativetopath" in image_data:
            image.setRelativeToPath(image_data["relativetopath"])
        if "brightness" in image_data:
            image.setBrightness(image_data["brightness"])
        return image

    data = node.userData("backgroundimages")
    if not data:
        return []

    try:
        images = json.loads(data)
    except json.decoder.JSONDecodeError:
        images = []

    if not raw:
        images = [_parse(_data) for _data in images]
    return images


def set_background_images(node, images):
    """Set hou.NetworkImage background images under given hou.Node

    Similar to: `nodegraphutils.loadBackgroundImages`

    """

    def _serialize(image):
        """Return hou.NetworkImage as serialized dict"""
        if isinstance(image, dict):
            # Assume already serialized, only do some minor validations
            if "path" not in image:
                raise ValueError("Missing `path` key in image dictionary.")
            if "rect" not in image:
                raise ValueError("Missing `rect` key in image dictionary.")
            if len(image["rect"]) != 4:
                raise ValueError("`rect` value must be list of four floats.")
            return image

        rect = image.rect()
        rect_min = rect.min()
        rect_max = rect.max()
        data = {
            "path": image.path(),
            "rect": [rect_min.x(), rect_min.y(), rect_max.x(), rect_max.y()],
        }
        if image.brightness() != 1.0:
            data["brightness"] = image.brightness()
        if image.relativeToPath():
            data["relativetopath"] = image.relativeToPath()
        return data

    with hou.undos.group('Edit Background Images'):
        if images:
            assert all(isinstance(image, (dict, hou.NetworkImage))
                       for image in images)
            data = json.dumps([_serialize(image) for image in images])
            node.setUserData("backgroundimages", data)
        else:
            node.destroyUserData("backgroundimages", must_exist=False)


def set_node_thumbnail(node, image_path, rect=None):
    """Set hou.NetworkImage attached to node.

    If an existing connected image is found it assumes that is the existing
    thumbnail and will update that particular instance instead.

    When `image_path` is None an existing attached `hou.NetworkImage` will be
    removed.

    Arguments:
        node (hou.Node): Node to set thumbnail for.
        image_path (Union[str, None]): Path to image to set.
            If None is set then the thumbnail will be removed if it exists.
        rect (hou.BoundingRect): Bounding rect for the relative placement
            to the node.

    Returns:
        hou.NetworkImage or None: The network image that was set or None if
            instead it not set or removed.

    """

    parent = node.parent()
    images = get_background_images(parent)

    node_path = node.path()
    # Find first existing image attached to node
    index, image = next(
        (
            (index, image) for index, image in enumerate(images) if
            image.relativeToPath() == node_path
        ),
        (None, None)
    )
    if image_path is None:
        # Remove image if it exists
        if image:
            images.remove(image)
            set_background_images(parent, images)
        return

    if rect is None:
        rect = hou.BoundingRect(-1, -1, 1, 1)

    if isinstance(image_path, hou.NetworkImage):
        image = image_path
        if index is not None:
            images[index] = image
        else:
            images.append(image)
    elif image is None:
        # Create the image
        image = hou.NetworkImage(image_path, rect)
        image.setRelativeToPath(node.path())
        images.append(image)
    else:
        # Update first existing image
        image.setRect(rect)
        image.setPath(image_path)

    set_background_images(parent, images)

    return image


def remove_all_thumbnails(node):
    """Remove all node thumbnails.

    Removes all network background images that are linked to the given node.
    """
    parent = node.parent()
    images = get_background_images(parent)
    node_path = node.path()
    images = [
        image for image in images if image.relativeToPath() != node_path
    ]
    set_background_images(parent, images)


def get_node_thumbnail(node, first_only=True):
    """Return node thumbnails.

    Return network background images that are linked to the given node.
    By default, only returns the first one found, unless `first_only` is False.

    Returns:
        Union[hou.NetworkImage, List[hou.NetworkImage]]:
            Connected network images

    """
    parent = node.parent()
    images = get_background_images(parent)
    node_path = node.path()

    def is_attached_to_node(image):
        return image.relativeToPath() == node_path

    attached_images = filter(is_attached_to_node, images)

    # Find first existing image attached to node
    if first_only:
        return next(attached_images, None)
    else:
        return attached_images


def find_active_network(category, default):
    """Find the first active network editor in the UI.

    If no active network editor pane is found at the given category then the
    `default` path will be used as fallback.

    For example, to find an active LOPs network:
    >>> network = find_active_network(
    ...     category=hou.lopNodeTypeCategory(),
    ...     fallback="/stage"
    ... )
    hou.Node("/stage/lopnet1")

    Arguments:
        category (hou.NodeTypeCategory): The node network category type.
        default (str): The default path to fallback to if no active pane
            is found with the given category, e.g. "/obj"

    Returns:
        hou.Node: The node network to return.

    """
    # Find network editors that are current tab of given category
    index = 0
    while True:
        pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor, index)
        if pane is None:
            break

        index += 1
        if not pane.isCurrentTab():
            continue

        pwd = pane.pwd()
        if pwd.type().category() != category:
            continue

        if not pwd.isEditable():
            continue

        return pwd

    # Default to the fallback if no valid candidate was found
    return hou.node(default)


def update_content_on_context_change():
    """Update all Creator instances to current asset"""
    host = registered_host()
    context = host.get_current_context()

    folder_path = context["folder_path"]
    task = context["task_name"]

    create_context = CreateContext(host, reset=True)

    for instance in create_context.instances:
        instance_folder_path = instance.get("folderPath")
        if instance_folder_path and instance_folder_path != folder_path:
            instance["folderPath"] = folder_path
        instance_task = instance.get("task")
        if instance_task and instance_task != task:
            instance["task"] = task

    create_context.save_changes()


def prompt_reset_context():
    """Prompt the user what context settings to reset.
    This prompt is used on saving to a different task to allow the scene to
    get matched to the new context.
    """
    # TODO: Cleanup this prototyped mess of imports and odd dialog
    from ayon_core.tools.attribute_defs.dialog import (
        AttributeDefinitionsDialog
    )
    from ayon_core.style import load_stylesheet
    from ayon_core.lib import BoolDef, UILabelDef

    definitions = [
        UILabelDef(
            label=(
                "You are saving your workfile into a different folder or task."
                "\n\n"
                "Would you like to update some settings to the new context?\n"
            )
        ),
        BoolDef(
            "fps",
            label="FPS",
            tooltip="Reset workfile FPS",
            default=True
        ),
        BoolDef(
            "frame_range",
            label="Frame Range",
            tooltip="Reset workfile start and end frame ranges",
            default=True
        ),
        BoolDef(
            "instances",
            label="Publish instances",
            tooltip="Update all publish instance's folder and task to match "
                    "the new folder and task",
            default=True
        ),
    ]

    dialog = AttributeDefinitionsDialog(definitions)
    dialog.setWindowTitle("Saving to different context.")
    dialog.setStyleSheet(load_stylesheet())
    if not dialog.exec_():
        return None

    options = dialog.get_values()
    if options["fps"] or options["frame_range"]:
        reset_framerange(
            fps=options["fps"],
            frame_range=options["frame_range"]
        )

    if options["instances"]:
        update_content_on_context_change()

    dialog.deleteLater()


def start_workfile_template_builder():
    from .workfile_template_builder import (
        build_workfile_template
    )

    log.info("Starting workfile template builder...")
    try:
        build_workfile_template(workfile_creation_enabled=True)
    except TemplateProfileNotFound:
        log.warning("Template profile not found. Skipping...")


def show_node_parmeditor(node):
    """Show Parameter Editor for the Node.

    Args:
        node (hou.Node): node instance
    """

    # Check if there's a floating parameter editor pane with its node set to the specified node.
    for tab in hou.ui.paneTabs():
        if (
            tab.type() == hou.paneTabType.Parm
            and tab.isFloating()
            and tab.currentNode() == node
        ):
            tab.setIsCurrentTab()
            return

    # We are using the hscript to create and set the network path of the pane
    # because hscript can set the node path without selecting the node.
    # Create a floating pane and set its name to the node path.
    hou.hscript(
        f"pane -F -m parmeditor -n {node.path()}"
    )
    # Hide network controls, turn linking off and set operator node path.
    hou.hscript(
        f"pane -a 1 -l 0 -H {node.path()} {node.path()}"
    )


def connect_file_parm_to_loader(file_parm: hou.Parm):
    """Connect the given file parm to a generic loader.
    If the parm is already connected to a generic loader node, go to that node.
    """
    
    from .pipeline import get_or_create_avalon_container

    referenced_parm = file_parm.getReferencedParm()

    # If the parm has reference
    if file_parm != referenced_parm:
        referenced_node = referenced_parm.getReferencedParm().node()
        if referenced_node.type().name() == "ayon::generic_loader::1.0":
            show_node_parmeditor(referenced_node)
            return

    # Create a generic loader node and reference its file parm
    main_container = get_or_create_avalon_container()
    
    node_name = f"{file_parm.node().name()}_{file_parm.name()}_loader"
    load_node = main_container.createNode("ayon::generic_loader",
                                          node_name=node_name)
    load_node.moveToGoodPosition()

    # Set relative reference via hscript. This avoids the issues of
    # `setExpression` e.g. having a keyframe.
    relative_path = file_parm.node().relativePathTo(load_node)
    expression = rf'chs\(\"{relative_path}/file\"\)'  # noqa
    hou.hscript(
        'opparm -r'
        f' {file_parm.node().path()} {file_parm.name()} \`{expression}\`'
    )
    show_node_parmeditor(load_node)
