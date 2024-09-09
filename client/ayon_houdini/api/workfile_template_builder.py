import hou

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.workfile.workfile_template_builder import (
    AbstractTemplateBuilder,
    PlaceholderPlugin
)
from ayon_core.tools.workfile_template_build import (
    WorkfileBuildPlaceholderDialog,
)
from ayon_core.tools.utils import show_message_dialog

from .lib import (
    imprint,
    lsattr,
    get_main_window
)
from .plugin import HoudiniCreator


class HoudiniTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for Houdini"""

    def resolve_template_path(self, path, fill_data):
        """Allows additional resolving over the template path using custom
        integration methods, like Houdini's expand string functionality.

        This only works with ayon-core 0.4.5+
        """
        # use default template data formatting
        path = super().resolve_template_path(path, fill_data)

        # escape backslashes for `expandString` and expand houdini vars
        path = path.replace("\\", "\\\\")
        path = hou.text.expandString(path)
        return path

    def import_template(self, path):
        """Import template into current scene.
        Block if a template is already loaded.

        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)

        Returns:
            bool: Whether the template was successfully imported or not
        """

        # TODO Check if template is already imported

        # Merge (Load) template workfile in the current scene.
        try: 
            hou.hipFile.merge(path, ignore_load_warnings=True)
            return True
        except hou.OperationFailed:
            return False


class HoudiniPlaceholderPlugin(PlaceholderPlugin):
    """Base Placeholder Plugin for Houdini with one unified cache.

    Inherited classes must still implement `populate_placeholder`
    """

    def get_placeholder_node_name(self, placeholder_data):
        return self.identifier.replace(".", "_")
    
    def create_placeholder_node(self, node_name=None):
        """Create node to be used as placeholder.

        By default, it creates a null node in '/out'.
        Feel free to override it in different workfile build plugins.
        """
 
        node = hou.node("/out").createNode(
            "null", node_name, force_valid_node_name=True)
        node.moveToGoodPosition()
        parms = node.parmTemplateGroup()
        for parm in {"execute", "renderdialog"}:
            p = parms.find(parm)
            p.hide(True)
            parms.replace(parm, p)
        node.setParmTemplateGroup(parms) 
        return node
    
    def create_placeholder(self, placeholder_data):
        
        node_name = self.get_placeholder_node_name(placeholder_data)

        placeholder_node = self.create_placeholder_node(node_name) 
        HoudiniCreator.customize_node_look(placeholder_node)

        placeholder_data["plugin_identifier"] = self.identifier
        
        imprint(placeholder_node, placeholder_data)
    
    def collect_scene_placeholders(self):
        # Read the cache by identifier
        placeholder_nodes = self.builder.get_shared_populate_data(
            self.identifier
        )
        if placeholder_nodes is None:
            placeholder_nodes = []

            nodes = lsattr("plugin_identifier", self.identifier)

            for node in nodes:
                placeholder_nodes.append(node)

            # Set the cache by identifier
            self.builder.set_shared_populate_data(
                    self.identifier, placeholder_nodes
                )
            
        return placeholder_nodes
    
    def update_placeholder(self, placeholder_item, placeholder_data):
        placeholder_node = hou.node(placeholder_item.scene_identifier)
        imprint(placeholder_node, placeholder_data, update=True)
        
        # Update node name
        node_name = self.get_placeholder_node_name(placeholder_data)
        node_name = hou.text.variableName(node_name)
        placeholder_node.setName(node_name, unique_name=True)

    def delete_placeholder(self, placeholder):
        placeholder_node = hou.node(placeholder.scene_identifier)
        placeholder_node.destroy()


def build_workfile_template(*args, **kwargs):
    # NOTE Should we inform users that they'll lose unsaved changes ?
    builder = HoudiniTemplateBuilder(registered_host())
    builder.build_template(*args, **kwargs)


def update_workfile_template(*args):
    builder = HoudiniTemplateBuilder(registered_host())
    builder.rebuild_template()


def create_placeholder(*args):
    host = registered_host()
    builder = HoudiniTemplateBuilder(host)
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.show()


def update_placeholder(*args):
    host = registered_host()
    builder = HoudiniTemplateBuilder(host)
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }
    placeholder_items = []
    for node in hou.selectedNodes():
        if node.path() in placeholder_items_by_id:
            placeholder_items.append(placeholder_items_by_id[node.path()])

    if len(placeholder_items) == 0:
        show_message_dialog(
            "Workfile Placeholder Manager", 
            "Please select a placeholder node.", 
            "warning", 
            get_main_window()
        )
        return

    if len(placeholder_items) > 1:
        show_message_dialog(
            "Workfile Placeholder Manager", 
            "Too many selected placeholder nodes.\n"
            "Please, Select one placeholder node.", 
            "warning", 
            get_main_window()
        )
        return

    placeholder_item = placeholder_items[0]
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.set_update_mode(placeholder_item)
    window.exec_()
