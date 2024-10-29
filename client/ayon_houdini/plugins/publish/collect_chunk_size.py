import pyblish.api
from ayon_core.lib import NumberDef
from ayon_core.pipeline import AYONPyblishPluginMixin
from ayon_houdini.api import plugin


class CollectChunkSize(plugin.HoudiniInstancePlugin,
                       AYONPyblishPluginMixin):
    """Collect chunk size for cache submission to Deadline."""

    order = pyblish.api.CollectorOrder + 0.05
    families = ["publish.hou"]
    targets = ["local", "remote"]
    label = "Collect Chunk Size"
    chunk_size = 999999

    def process(self, instance):
        # need to get the chunk size info from the setting
        attr_values = self.get_attr_values_from_data(instance.data)
        instance.data["chunkSize"] = attr_values.get("chunkSize")

    @classmethod
    def get_attr_defs_for_instance(cls, create_context, instance):
        # Filtering of instance, if needed, can be customized
        if not cls.instance_matches_plugin_families(instance):
            return []

        # Attributes logic
        creator_attributes = instance["creator_attributes"]

        visible = creator_attributes.get("farm", False)

        return [
            NumberDef("chunkSize",
                      minimum=1,
                      maximum=999999,
                      decimals=0,
                      default=cls.chunk_size,
                      label="Frame Per Task",
                      visible=visible)
        ]

    @classmethod
    def register_create_context_callbacks(cls, create_context):
        create_context.add_value_changed_callback(cls.on_values_changed)

    @classmethod
    def on_values_changed(cls, event):
        """Update instance attribute definitions on attribute changes."""

        # Update attributes if any of the following plug-in attributes
        # change:
        keys = ["farm"]

        for instance_change in event["changes"]:
            instance = instance_change["instance"]
            if not cls.instance_matches_plugin_families(instance):
                continue
            value_changes = instance_change["changes"]
            plugin_attribute_changes = (
                value_changes.get("creator_attributes", {})
                .get(cls.__name__, {}))

            if not any(key in plugin_attribute_changes for key in keys):
                continue

            # Update the attribute definitions
            new_attrs = cls.get_attr_defs_for_instance(
                event["create_context"], instance
            )
            instance.set_publish_plugin_attr_defs(cls.__name__, new_attrs)