from ayon_core.pipeline.workfile.workfile_template_builder import (
    LoadPlaceholderItem,
    PlaceholderLoadMixin,
)

from ayon_houdini.api.workfile_template_builder import (
    HoudiniPlaceholderPlugin
)
from ayon_houdini.api.lib import read


class HoudiniPlaceholderLoadPlugin(
    HoudiniPlaceholderPlugin, PlaceholderLoadMixin
):
    """Workfile template plugin to create "load placeholders".

    "load placeholders" will be replaced by AYON products.

    """

    identifier = "ayon.load.placeholder"
    label = "Houdini Load"

    def populate_placeholder(self, placeholder):
        self.populate_load_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        self.populate_load_placeholder(placeholder)

    def get_placeholder_options(self, options=None):
        return self.get_load_plugin_options(options)
    
    def get_placeholder_node_name(self, placeholder_data):

        node_name = "{}_{}".format(
            self.identifier.replace(".", "_"),
            placeholder_data["product_name"]
        )
        return node_name

    def collect_placeholders(self):
        output = []
        load_placeholders = self.collect_scene_placeholders()
        
        for node in load_placeholders:
            placeholder_data = read(node)
            output.append(
                LoadPlaceholderItem(node.path(), placeholder_data, self)
            )

        return output
    