# -*- coding: utf-8 -*-
"""Integrate the AYON parameters into the published HDA definition."""
import os

import hou
import pyblish.api

from ayon_api import get_representation_by_name
from ayon_core.pipeline import get_current_project_name
from ayon_houdini.api import lib


class IntegrateHDA(pyblish.api.InstancePlugin):
    """Store the AYON parameters on the published HDA definition.

    The HDA file is written during extraction, before the representation
    entity exists, so the representation id is not known at that point. This
    integrator runs after the HDA has been integrated - the file is in its
    final location and the representation exists - and stores `project_name`
    and `representation` on the HDA definition inside the published file.

    Because they are part of the HDA definition, the values also change when
    the definition is switched, e.g. to another published version. The values
    are plain static strings, no parameter expressions are involved.
    """

    order = pyblish.api.IntegratorOrder + 0.1
    label = "Integrate HDA"
    families = ["hda"]

    def process(self, instance):

        representation = next(
            (
                repre
                for repre in instance.data.get("representations", [])
                if repre.get("name") == "hda"
            ),
            None,
        )
        if representation is None:
            self.log.debug("No HDA representation to integrate.")
            return

        version_entity = instance.data.get("versionEntity")
        if not version_entity:
            self.log.warning(
                "No integrated version found. The AYON parameters are not "
                "stored on the HDA definition."
            )
            return

        published_path = representation.get("published_path")
        if not published_path or not os.path.exists(published_path):
            self.log.warning(
                "Published HDA file does not exist: {}".format(published_path)
            )
            return

        project_name = get_current_project_name()
        representation_id = self._get_representation_id(
            project_name, representation["name"], version_entity["id"]
        )
        if representation_id is None:
            self.log.warning(
                "Could not find representation '{}' of the integrated "
                "version. The AYON parameters are not stored on the HDA "
                "definition.".format(representation["name"])
            )
            return

        self.log.debug("Storing AYON parameters in: {}".format(published_path))
        self._store_parameters(
            hda_file_path=published_path,
            project_name=project_name,
            representation_id=representation_id,
        )

    def _get_representation_id(
        self, project_name, representation_name, version_id
    ):
        """Get the id of the integrated representation.

        Args:
            project_name (str): Name of the project.
            representation_name (str): Name of the representation.
            version_id (str): Id of the version the representation belongs to.

        Returns:
            Union[str, None]: Representation id, or None when not found.
        """
        try:
            repre_entity = get_representation_by_name(
                project_name,
                representation_name,
                version_id,
                fields=["id"],
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning(
                "Failed to query the '{}' representation: {}".format(
                    representation_name, exc
                )
            )
            return None

        if not repre_entity:
            return None
        return repre_entity["id"]

    def _store_parameters(
        self, hda_file_path, project_name, representation_id
    ):
        """Store the AYON parameters on the HDA definitions in the file.

        Args:
            hda_file_path (str): Path of the published HDA file.
            project_name (str): Name of the project.
            representation_id (str): Id of the representation.

        Returns:
            None
        """
        hou.hda.installFile(hda_file_path)
        definitions = hou.hda.definitionsInFile(hda_file_path)
        if not definitions:
            self.log.warning(
                "No HDA definitions found in: {}".format(hda_file_path)
            )
            return

        values = {
            "project_name": project_name,
            "representation": representation_id,
        }
        for definition in definitions:
            parm_group = definition.parmTemplateGroup()
            parm_folder = parm_group.findFolder("Extra")
            parm_templates = []
            if parm_folder is not None:
                # Keep parameter templates that are not managed by AYON
                parm_templates = [
                    parm_template
                    for parm_template in parm_folder.parmTemplates()
                    if parm_template.name() not in lib.AYON_DEFINITION_PARMS
                ]
            parm_templates.extend(
                hou.StringParmTemplate(
                    parm_name,
                    parm_name,
                    1,
                    default_value=(values[parm_name],),
                )
                for parm_name in lib.AYON_DEFINITION_PARMS
            )
            parm_folder = hou.FolderParmTemplate(
                "folder", "Extra", parm_templates=parm_templates
            )
            if parm_group.findFolder("Extra") is None:
                parm_group.append(parm_folder)
            else:
                parm_group.replace(parm_folder.name(), parm_folder)

            definition.setParmTemplateGroup(parm_group)
            # Save each definition back into the HDA file
            definition.save(hda_file_path)
