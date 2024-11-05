import inspect

from ayon_houdini.api import plugin
from ayon_core.pipeline import CreatedInstance, CreatorError

import hou


class CreateUSDComponentBuilder(plugin.HoudiniCreator):
    identifier = "io.ayon.creators.houdini.componentbuilders"
    label = "USD Component Builder LOPs"
    product_type = "usd"
    icon = "cubes"
    description = "Create USD from Component Builder LOPs"

    def get_detail_description(self):
        return inspect.cleandoc("""
            Creates a USD publish from a Component Output LOP that is part of 
            a solaris component builder network.
            
            The created USD will contain the component builder LOPs and all its
            dependencies inside the single product.
            
            To use it, select a Component Output LOP and click "Create" for
            this creator. It will generate an instance for each selected
            Component Output LOP.
        """)

    def create(self, product_name, instance_data, pre_create_data):

        nodes = hou.selectedNodes()

        builders = [
            node for node in nodes if node.type().name() == "componentoutput"
        ]
        if not builders:
            return

        for builder in builders:
            self.create_for_instance_node(product_name, instance_data, builder)


    def create_for_instance_node(
            self, product_name, instance_data, instance_node):

        try:
            self.customize_node_look(instance_node)
            instance_data["instance_node"] = instance_node.path()
            instance_data["instance_id"] = instance_node.path()
            instance_data["families"] = self.get_publish_families()
            instance = CreatedInstance(
                self.product_type,
                product_name,
                instance_data,
                self)
            self._add_instance_to_context(instance)
            self.imprint(instance_node, instance.data_to_store())
        except hou.Error as er:
            raise CreatorError("Creator error: {}".format(er)) from er

        # Lock any parameters in this list
        to_lock = [
            # Lock some AYON attributes
            "productType",
            "id",
        ]
        self.lock_parameters(instance_node, to_lock)

    def get_network_categories(self):
        # Do not expose via tab menu because currently it does not create any
        # node, but only 'imprints' on an existing node.
        return []

    def get_publish_families(self):
        return ["usd", "componentbuilder"]
