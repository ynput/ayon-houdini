from ayon_core.pipeline.workfile.workfile_template_builder import (
    CreatePlaceholderItem,
    PlaceholderCreateMixin,
)
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext

from ayon_houdini.api.workfile_template_builder import (
    HoudiniPlaceholderPlugin
)
from ayon_houdini.api.lib import read


class HoudiniPlaceholderCreatePlugin(
    HoudiniPlaceholderPlugin, PlaceholderCreateMixin
):
    """Workfile template plugin to create "create placeholders".

    "create placeholders" will be replaced by publish instances.

    TODO:
        Support imprint & read precreate data to instances.
    """

    identifier = "ayon.create.placeholder"
    label = "Houdini Create"

    def populate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder)

    def get_placeholder_options(self, options=None):
        return self.get_create_plugin_options(options)
    
    def get_placeholder_node_name(self, placeholder_data):
        create_context = CreateContext(registered_host())
        creator = create_context.creators.get(placeholder_data["creator"])
        product_type = creator.product_type
        node_name = "{}_{}".format(self.identifier.replace(".", "_"), product_type)

        return node_name

    def collect_placeholders(self):
        output = []
        create_placeholders = self.collect_scene_placeholders()

        for node in create_placeholders:
            placeholder_data = read(node)
            output.append(
                CreatePlaceholderItem(node.path(), placeholder_data, self)
            )

        return output
    