from ayon_core.pipeline import InventoryAction

import hou


class SelectInScene(InventoryAction):
    """Select nodes in the scene from selected containers in scene inventory"""

    label = "Select in scene"
    icon = "search"
    color = "#888888"
    order = 99

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
        nodes = [hou.node(container["objectName"]) for container in containers]
        if not nodes:
            return

        hou.clearAllSelected()
        for node in nodes:
            node.setSelected(True)

        # Set last as current
        nodes[-1].setCurrent(True)
