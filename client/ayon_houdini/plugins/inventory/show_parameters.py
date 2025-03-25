from ayon_core.pipeline import InventoryAction
from ayon_houdini.api.lib import show_node_parmeditor

import hou


class ShowParametersAction(InventoryAction):

    label = "Show parameters"
    icon = "pencil-square-o"
    color = "#888888"
    order = 100

    @staticmethod
    def is_compatible(container) -> bool:
        object_name: str = container.get("objectName")
        if not object_name:
            return False

        node = hou.node(object_name)
        if not node:
            return False

        return True

    def process(self, containers):
        for container in containers:
            node = hou.node(container["objectName"])
            show_node_parmeditor(node)
