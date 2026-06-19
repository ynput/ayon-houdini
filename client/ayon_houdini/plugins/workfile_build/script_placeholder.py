from ayon_houdini.api.lib import find_active_network
from ayon_houdini.api.workfile_template_builder import (
    HoudiniPlaceholderPlugin
)
from ayon_core.lib import NumberDef, TextDef
from ayon_core.lib.events import weakref_partial

import hou


EXAMPLE_SCRIPT = """
import hou

# Access the placeholder node (also via hou.pwd())
placeholder_identifier = placeholder.scene_identifier
placeholder_node = hou.node(placeholder_identifier)

# Access the event callback
if event is None:
    print(f"Populating {placeholder}")
else:
    if event.topic == "template.depth_processed":
        print(f"Processed depth: {event.get('depth')}")
    elif event.topic == "template.finished":
        print("Build finished.")
""".strip()


class HoudiniPlaceholderScriptPlugin(HoudiniPlaceholderPlugin):
    """Execute a script at the given `order` during workfile build.

    This is a very low-level placeholder to run Python scripts at a given
    point in time during the workfile template build.

    """

    identifier = "houdini.runscript"
    label = "Run Python Script"

    def get_placeholder_options(self, options=None):
        options = options or {}
        return [
            NumberDef(
                "order",
                label="Order",
                default=options.get("order") or 0,
                decimals=0,
                minimum=0,
                maximum=999,
                tooltip=(
                    "Order"
                    "\nOrder defines asset loading priority (0 to 999)"
                    "\nPriority rule is : \"lowest is first to load\"."
                )
            ),
            TextDef(
                "prepare_script",
                label="Run at\nprepare",
                tooltip="Run before populate at prepare order",
                multiline=True,
                default=options.get("prepare_script", "")
            ),
            TextDef(
                "populate_script",
                label="Run at\npopulate",
                tooltip="Run script at populate node order<br>"
                        "This is the <b>default</b> behavior",
                multiline=True,
                default=options.get("populate_script", EXAMPLE_SCRIPT)
            ),
            TextDef(
                "depth_processed_script",
                label="Run after\ndepth\niteration",
                tooltip="Run script after every build depth iteration",
                multiline=True,
                default=options.get("depth_processed_script", "")
            ),
            TextDef(
                "finished_script",
                label="Run after\nbuild",
                tooltip=(
                    "Run script at build finished.<br>"
                    "<b>Note</b>: this even runs if other placeholders had "
                    "errors during the build"
                ),
                multiline=True,
                default=options.get("finished_script", "")
            ),
        ]

    def prepare_placeholders(self, placeholders):
        super().prepare_placeholders(placeholders)
        for placeholder in placeholders:
            prepare_script = placeholder.data.get("prepare_script")
            if not prepare_script:
                continue

            self.run_script(placeholder, prepare_script)

    def populate_placeholder(self, placeholder):
        populate_script = placeholder.data.get("populate_script")
        depth_script = placeholder.data.get("depth_processed_script")
        finished_script = placeholder.data.get("finished_script")

        # Enforce value not being a float
        order = int(placeholder.order)

        # Run now
        if populate_script:
            self.run_script(placeholder, populate_script)

        if not any([depth_script, finished_script]):
            # No callback scripts to run
            if not placeholder.data.get("keep_placeholder", True):
                self.delete_placeholder(placeholder)
            return

        # Run at each depth processed
        if depth_script:
            callback = weakref_partial(
                self.run_script, placeholder, depth_script)
            self.builder.add_on_depth_processed_callback(
                callback, order=order)

        # Run at build finish
        if finished_script:
            callback = weakref_partial(
                self.run_script, placeholder, finished_script)
            self.builder.add_on_finished_callback(
                callback, order=order)

        # If placeholder should be deleted, delete it after finish so
        # the scripts have access to it up to the last run
        if not placeholder.data.get("keep_placeholder", True):
            delete_callback = weakref_partial(
                self.delete_placeholder, placeholder)
            self.builder.add_on_finished_callback(
                delete_callback, order=order + 1)

    def run_script(self, placeholder, script, event=None):
        """Run script

        Even though `placeholder` is an unused arguments by exposing it as
        an input argument it means it makes it available through
        globals()/locals() in the `exec` call, giving the script access
        to the placeholder.

        For example:
        >>> node = placeholder.scene_identifier

        In the case the script is running at a callback level (not during
        populate) then it has access to the `event` as well, otherwise the
        value is None if it runs during `populate_placeholder` directly.

        For example adding this as the callback script:
        >>> if event is not None:
        >>>     if event.topic == "on_depth_processed":
        >>>         print(f"Processed depth: {event.get('depth')}")
        >>>     elif event.topic == "on_finished":
        >>>         print("Build finished.")

        """
        self.log.debug(f"Running script at event: {event}")

        # Set current node so script can easily access the node via `hou.pwd()`
        original_pwd = hou.pwd()
        try:
            hou.cd(placeholder.scene_identifier)
            exec(script, locals())
        finally:
            try:
                hou.setPwd(original_pwd)
            except hou.Error:
                pass

    def create_placeholder_node(self, node_name=None) -> hou.Node:
        """Create node to be used as placeholder.

        Create it in the first valid panel the user has open, if none found
        than fallback to `/obj`. By creating it in the current network the
        user is working in, it will adapt the null to the relevant type the
        user may want to run the scripts in - getting a better context.
        """
        categories = hou.nodeTypeCategories()

        # Consider only categories that support a `null` node type.
        categories = {
            name: category for name, category in categories.items()
            if category.nodeType("null")
        }

        # Prioritize certain categories
        order = ["Sop", "Lop", "Object", "Cop", "Cop2", "Driver", "Top"]
        order = {key: index for index, key in enumerate(order)}
        categories = {
            name: category for name, category
            in sorted(categories.items(), key=lambda x: order.get(x[0], 1000))
        }

        for category in categories.values():
            network = find_active_network(category, default=None)
            if network is not None:
                break
        else:
            network = hou.node("/obj")

        node = network.createNode(
            "null", node_name, force_valid_node_name=True)
        node.moveToGoodPosition()
        parms = node.parmTemplateGroup()
        for parm in {"execute", "renderdialog"}:
            p = parms.find(parm)
            if p:
                p.hide(True)
                parms.replace(parm, p)
        node.setParmTemplateGroup(parms)
        return node
