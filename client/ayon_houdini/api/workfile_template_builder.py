import os 

import hou

from ayon_core.lib import (
    StringTemplate,
    filter_profiles,
)
from ayon_core.pipeline import registered_host, Anatomy
from ayon_core.pipeline.workfile.workfile_template_builder import (
    AbstractTemplateBuilder,
    PlaceholderPlugin,
    TemplateProfileNotFound,
    TemplateLoadFailed,
    TemplateNotFound
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
    
    def get_template_preset(self):
        """Unified way how template preset is received using settings.

        Method is dependent on '_get_build_profiles' which should return filter
        profiles to resolve path to a template. Default implementation looks
        into host settings:
        - 'project_settings/{host name}/templated_workfile_build/profiles'

        Returns:
            dict: Dictionary with `path`, `keep_placeholder` and
                `create_first_version` settings from the template preset
                for current context.

        Raises:
            TemplateProfileNotFound: When profiles are not filled.
            TemplateLoadFailed: Profile was found but path is not set.
            TemplateNotFound: Path was set but file does not exist.
        """

        host_name = self.host_name
        project_name = self.project_name
        task_name = self.current_task_name
        task_type = self.current_task_type

        build_profiles = self._get_build_profiles()
        profile = filter_profiles(
            build_profiles,
            {
                "task_types": task_type,
                "task_names": task_name
            }
        )

        if not profile:
            raise TemplateProfileNotFound((
                "No matching profile found for task '{}' of type '{}' "
                "with host '{}'"
            ).format(task_name, task_type, host_name))

        path = profile["path"]

        # switch to remove placeholders after they are used
        keep_placeholder = profile.get("keep_placeholder")
        create_first_version = profile.get("create_first_version")

        # backward compatibility, since default is True
        if keep_placeholder is None:
            keep_placeholder = True

        if not path:
            raise TemplateLoadFailed((
                "Template path is not set.\n"
                "Path need to be set in {}\\Template Workfile Build "
                "Settings\\Profiles"
            ).format(host_name.title()))

        # Try fill path with environments and anatomy roots
        anatomy = Anatomy(project_name)
        fill_data = {
            key: value
            for key, value in os.environ.items()
        }

        fill_data["root"] = anatomy.roots
        fill_data["project"] = {
            "name": project_name,
            "code": anatomy.project_code,
        }

        result = StringTemplate.format_template(path, fill_data)
        if result.solved:
            path = result.normalized()

        # I copied the whole thing because I wanted to add some
        # Houdini specific code here
        path = hou.text.expandString(path)

        if path and os.path.exists(path):
            self.log.info("Found template at: '{}'".format(path))
            return {
                "path": path,
                "keep_placeholder": keep_placeholder,
                "create_first_version": create_first_version
            }

        solved_path = None
        while True:
            try:
                solved_path = anatomy.path_remapper(path)
            except KeyError as missing_key:
                raise KeyError(
                    "Could not solve key '{}' in template path '{}'".format(
                        missing_key, path))

            if solved_path is None:
                solved_path = path
            if solved_path == path:
                break
            path = solved_path

        solved_path = os.path.normpath(solved_path)
        if not os.path.exists(solved_path):
            raise TemplateNotFound(
                "Template found in AYON settings for task '{}' with host "
                "'{}' does not exists. (Not found : {})".format(
                    task_name, host_name, solved_path))

        self.log.info("Found template at: '{}'".format(solved_path))

        return {
            "path": solved_path,
            "keep_placeholder": keep_placeholder,
            "create_first_version": create_first_version
        }

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
 
        node = hou.node("/out").createNode("null", node_name)
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
        placeholder_node.setName(node_name, unique_name=True)

    def delete_placeholder(self, placeholder):
        placeholder_node = hou.node(placeholder.scene_identifier)
        placeholder_node.destroy()


def build_workfile_template(*args):
    # NOTE Should we inform users that they'll lose unsaved changes ?
    builder = HoudiniTemplateBuilder(registered_host())
    builder.build_template()


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
