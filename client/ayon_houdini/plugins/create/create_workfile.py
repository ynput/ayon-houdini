# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
from ayon_houdini.api import plugin
from ayon_houdini.api.lib import read, imprint
from ayon_houdini.api.pipeline import CONTEXT_CONTAINER
from ayon_core.pipeline import CreatedInstance, AutoCreator
import hou


class CreateWorkfile(plugin.HoudiniCreatorBase, AutoCreator):
    """Workfile auto-creator."""
    identifier = "io.openpype.creators.houdini.workfile"
    label = "Workfile"
    product_type = "workfile"
    icon = "fa5.file"

    default_variant = "Main"

    def create(self):
        variant = self.default_variant
        current_instance = next(
            (
                instance for instance in self.create_context.instances
                if instance.creator_identifier == self.identifier
            ), None)

        project_entity = self.create_context.get_current_project_entity()
        project_name = project_entity["name"]
        folder_entity = self.create_context.get_current_folder_entity()
        folder_path = folder_entity["path"]
        task_entity = self.create_context.get_current_task_entity()
        task_name = task_entity["name"]
        host_name = self.create_context.host_name

        if current_instance is None:
            product_name = self.get_product_name(
                project_name,
                folder_entity,
                task_entity,
                variant,
                host_name,
            )
            data = {
                "folderPath": folder_path,
                "task": task_name,
                "variant": variant,
            }

            data.update(
                self.get_dynamic_data(
                    project_name,
                    folder_entity,
                    task_entity,
                    variant,
                    host_name,
                    current_instance)
            )
            self.log.info("Auto-creating workfile instance...")
            current_instance = CreatedInstance(
                self.product_type, product_name, data, self
            )
            self._add_instance_to_context(current_instance)
        elif (
            current_instance["folderPath"] != folder_path
            or current_instance["task"] != task_name
        ):
            # Update instance context if is not the same
            product_name = self.get_product_name(
                project_name,
                folder_entity,
                task_entity,
                variant,
                host_name,
            )
            current_instance["folderPath"] = folder_path
            current_instance["task"] = task_name
            current_instance["productName"] = product_name

        # write workfile information to context container.
        op_ctx = hou.node(CONTEXT_CONTAINER)
        if not op_ctx:
            op_ctx = self.host.create_context_node()

        workfile_data = {"workfile": current_instance.data_to_store()}
        imprint(op_ctx, workfile_data)

    def collect_instances(self):
        op_ctx = hou.node(CONTEXT_CONTAINER)
        instance = read(op_ctx)
        if not instance:
            return
        workfile = instance.get("workfile")
        if not workfile:
            return
        created_instance = CreatedInstance.from_existing(
            workfile, self
        )
        self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        op_ctx = hou.node(CONTEXT_CONTAINER)
        for created_inst, _changes in update_list:
            if created_inst["creator_identifier"] == self.identifier:
                workfile_data = {"workfile": created_inst.data_to_store()}
                imprint(op_ctx, workfile_data, update=True)
