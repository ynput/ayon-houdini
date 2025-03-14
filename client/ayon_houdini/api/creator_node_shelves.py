"""Library to register OpenPype Creators for Houdini TAB node search menu.

This can be used to install custom houdini tools for the TAB search
menu which will trigger a publish instance to be created interactively.

The Creators are automatically registered on launch of Houdini through the
Houdini integration's `host.install()` method.

"""
import contextlib
import tempfile
import logging
import os

import ayon_api

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext
from ayon_core.resources import get_ayon_icon_filepath

import hou
import stateutils
import soptoolutils
import loptoolutils
import cop2toolutils


log = logging.getLogger(__name__)

CATEGORY_GENERIC_TOOL = {
    hou.sopNodeTypeCategory(): soptoolutils.genericTool,
    hou.cop2NodeTypeCategory(): cop2toolutils.genericTool,
    hou.lopNodeTypeCategory(): loptoolutils.genericTool
}


CREATE_SCRIPT = """
from ayon_houdini.api.creator_node_shelves import create_interactive
create_interactive("{identifier}", **kwargs)
"""


def create_interactive(creator_identifier, **kwargs):
    """Create a Creator using its identifier interactively.

    This is used by the generated shelf tools as callback when a user selects
    the creator from the node tab search menu.

    The `kwargs` should be what Houdini passes to the tool create scripts
    context. For more information see:
    https://www.sidefx.com/docs/houdini/hom/tool_script.html#arguments

    Args:
        creator_identifier (str): The creator identifier of the Creator plugin
            to create.

    Return:
        list: The created instances.

    """
    host = registered_host()
    context = CreateContext(host)
    creator = context.manual_creators.get(creator_identifier)
    if not creator:
        raise RuntimeError("Invalid creator identifier: {}".format(
            creator_identifier)
        )

    # TODO Use Qt instead
    result, variant = hou.ui.readInput(
        "Define variant name",
        buttons=("Ok", "Cancel"),
        initial_contents=creator.get_default_variant(),
        title="Define variant",
        help="Set the variant for the publish instance",
        close_choice=1
    )

    if result == 1:
        # User interrupted
        return

    variant = variant.strip()
    if not variant:
        raise RuntimeError("Empty variant value entered.")

    # TODO: Once more elaborate unique create behavior should exist per Creator
    #   instead of per network editor area then we should move this from here
    #   to a method on the Creators for which this could be the default
    #   implementation.
    pane = stateutils.activePane(kwargs)
    is_null_created = False
    if isinstance(pane, hou.NetworkEditor):
        pwd = pane.pwd()
        project_name = context.get_current_project_name()
        folder_path = context.get_current_folder_path()
        task_name = context.get_current_task_name()
        folder_entity = ayon_api.get_folder_by_path(
            project_name, folder_path
        )
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )
        product_name = creator.get_product_name(
            project_name=context.get_current_project_name(),
            folder_entity=folder_entity,
            task_entity=task_entity,
            variant=variant,
            host_name=context.host_name,
        )

        tool_fn = CATEGORY_GENERIC_TOOL.get(pwd.childTypeCategory())
        if tool_fn is not None:
            out_null = tool_fn(kwargs, "null")
            # TODO: For whatever reason the code does not continue if the
            #  user cancels the operation with escape; yet also no error seems
            #  to be raised.
            if out_null:
                out_null.setName("OUT_{}".format(product_name),
                                 unique_name=True)
                is_null_created = True

    before = context.instances_by_id.copy()

    # Create the instance
    context.create(
        creator_identifier=creator_identifier,
        variant=variant,
        pre_create_data={"use_selection": True}
    )

    # For convenience we set the new node as current since that's much more
    # familiar to the artist when creating a node interactively. However
    # we do not select it if the user used the "null" place down functionality
    # TODO Allow to disable auto-select in studio settings or user preferences
    #  allow to choose:
    #  - always select instance node
    #  - never select instance node
    #  - select null if created else select instance node (current default)
    after = context.instances_by_id
    new = set(after) - set(before)
    if new and not is_null_created:
        # Select the new instance
        for instance_id in new:
            instance = after[instance_id]
            node = hou.node(instance.get("instance_node"))
            node.setCurrent(True)

    return list(new)


@contextlib.contextmanager
def shelves_change_block():
    """Write shelf changes at the end of the context."""
    hou.shelves.beginChangeBlock()
    try:
        yield
    finally:
        hou.shelves.endChangeBlock()


def install():
    """Install the Creator plug-ins to show in Houdini's TAB node search menu.

    This function is re-entrant and can be called again to reinstall and
    update the node definitions. For example during development it can be
    useful to call it manually:
        >>> from ayon_houdini.api.creator_node_shelves import install
        >>> install()

    Returns:
        list: List of `hou.Tool` instances

    """

    host = registered_host()

    # Store the filepath on the host
    # TODO: Define a less hacky static shelf path for current houdini session
    filepath_attr = "_creator_node_shelf_filepath"
    filepath = getattr(host, filepath_attr, None)
    if filepath is None:
        f = tempfile.NamedTemporaryFile(prefix="houdini_creator_nodes_",
                                        suffix=".shelf",
                                        delete=False)
        f.close()
        filepath = f.name
        setattr(host, filepath_attr, filepath)
    elif os.path.exists(filepath):
        # Remove any existing shelf file so that we can completey regenerate
        # and update the tools file if creator identifiers change
        os.remove(filepath)

    icon = get_ayon_icon_filepath()
    tab_menu_label = os.environ.get("AYON_MENU_LABEL") or "AYON"

    # Create context only to get creator plugins, so we don't reset and only
    # populate what we need to retrieve the list of creator plugins
    create_context = CreateContext(host, reset=False)
    create_context.reset_current_context()
    create_context._reset_creator_plugins()

    log.debug("Writing OpenPype Creator nodes to shelf: {}".format(filepath))
    tools = []

    with shelves_change_block():
        for identifier, creator in create_context.manual_creators.items():

            # Allow the creator plug-in itself to override the categories
            # for where they are shown with `Creator.get_network_categories()`
            if not hasattr(creator, "get_network_categories"):
                log.debug("Creator {} has no `get_network_categories` method "
                          "and will not be added to TAB search.")
                continue

            network_categories = creator.get_network_categories()
            if not network_categories:
                continue

            key = "ayon_create.{}".format(identifier)
            log.debug(f"Registering {key}")
            script = CREATE_SCRIPT.format(identifier=identifier)
            data = {
                "script": script,
                "language": hou.scriptLanguage.Python,
                "icon": icon,
                "help": "Create Ayon publish instance for {}".format(
                    creator.label
                ),
                "help_url": None,
                "network_categories": network_categories,
                "viewer_categories": [],
                "cop_viewer_categories": [],
                "network_op_type": None,
                "viewer_op_type": None,
                "locations": [tab_menu_label]
            }
            label = "Create {}".format(creator.label)
            tool = hou.shelves.tool(key)
            if tool:
                tool.setData(**data)
                tool.setLabel(label)
            else:
                tool = hou.shelves.newTool(
                    file_path=filepath,
                    name=key,
                    label=label,
                    **data
                )

            tools.append(tool)

    # Ensure the shelf is reloaded
    hou.shelves.loadFile(filepath)

    return tools
