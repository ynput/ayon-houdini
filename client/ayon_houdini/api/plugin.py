# -*- coding: utf-8 -*-
"""Houdini specific AYON/Pyblish plugin definitions."""
import os
from typing import Dict, Optional

import hou

import clique
import pyblish.api
from ayon_core.pipeline import (
    CreatorError,
    Creator,
    CreatedInstance,
    AYON_INSTANCE_ID,
    AVALON_INSTANCE_ID,
    load,
    publish,
)
from ayon_core.lib import BoolDef
from ayon_core.pipeline.staging_dir import StagingDir

from .lib import (
    imprint, read, lsattr, render_rop,
    add_self_publish_button,
    expand_houdini_string,
)
from .usd import get_ayon_entity_uri_from_representation_context


SETTINGS_CATEGORY = "houdini"

REMAP_CREATOR_IDENTIFIERS: Dict[str, str] = {
    "io.openpype.creators.houdini.ass":
        "io.ayon.creators.houdini.ass",
    "io.openpype.creators.houdini.arnold_rop":
        "io.ayon.creators.houdini.arnold_rop",
    "io.openpype.creators.houdini.bgeo":
        "io.ayon.creators.houdini.bgeo",
    "io.openpype.creators.houdini.camera":
        "io.ayon.creators.houdini.camera",
    "io.openpype.creators.houdini.hda": "io.ayon.creators.houdini.hda",
    "io.openpype.creators.houdini.imagesequence":
        "io.ayon.creators.houdini.imagesequence",
    "io.openpype.creators.houdini.karma_rop":
        "io.ayon.creators.houdini.karma_rop",
    "io.openpype.creators.houdini.mantra_rop":
        "io.ayon.creators.houdini.mantra_rop",
    "io.openpype.creators.houdini.model": "io.ayon.creators.houdini.model",
    "io.openpype.creators.houdini.pointcache":
        "io.ayon.creators.houdini.pointcache",
    "io.openpype.creators.houdini.redshiftproxy":
        "io.ayon.creators.houdini.redshiftproxy",
    "io.openpype.creators.houdini.redshift_rop":
        "io.ayon.creators.houdini.redshift_rop",
    "io.openpype.creators.houdini.review": "io.ayon.creators.houdini.review",
    "io.openpype.creators.houdini.staticmesh.fbx":
        "io.ayon.creators.houdini.staticmesh.fbx",
    "io.openpype.creators.houdini.usd": "io.ayon.creators.houdini.usd",
    "io.openpype.creators.houdini.usd.look":
        "io.ayon.creators.houdini.usd.look",
    "io.openpype.creators.houdini.usdrender":
        "io.ayon.creators.houdini.usdrender",
    "io.openpype.creators.houdini.vray_rop":
        "io.ayon.creators.houdini.vray_rop",
    "io.openpype.creators.houdini.vdbcache":
        "io.ayon.creators.houdini.vdbcache",
    "io.openpype.creators.houdini.workfile":
        "io.ayon.creators.houdini.workfile",
}

# For backwards compatibility starting from ayon-houdini 0.4.6 we will
# remap the AYON creator identifiers to their legacy ones. This way, for the
# time being no remapping occurs yet. But it will allow for a few releases to
# occur that could still open scenes with the newer identifiers if a user needs
# to downgrade versions.
# When removing this all the Creators should update their `identifier` to the
# new identifier too.
REMAP_CREATOR_IDENTIFIERS = {
    new: old for old, new in REMAP_CREATOR_IDENTIFIERS.items()
}


class HoudiniCreatorBase(object):
    @staticmethod
    def cache_instance_data(shared_data):
        """Cache instances for Creators to shared data.

        Create `houdini_cached_instances` key when needed in shared data and
        fill it with all collected instances from the scene under its
        respective creator identifiers.

        Create `houdini_cached_legacy_instance` key for any legacy instances
        detected in the scene as instances per product type (legacy: family).

        Args:
            Dict[str, Any]: Shared data.

        """
        if shared_data.get("houdini_cached_instances") is None:
            cache = dict()
            cache_legacy = dict()

            nodes = []
            for id_type in [AYON_INSTANCE_ID, AVALON_INSTANCE_ID]:
                nodes.extend(lsattr("id", id_type))
            for node in nodes:

                creator_identifier_parm = node.parm("creator_identifier")
                if creator_identifier_parm:
                    # creator instance
                    creator_id = creator_identifier_parm.eval()

                    # Allow legacy creator identifiers to be remapped
                    creator_id = REMAP_CREATOR_IDENTIFIERS.get(
                        creator_id, creator_id)

                    cache.setdefault(creator_id, []).append(node)

                else:
                    # legacy instance
                    family_parm = node.parm("family")
                    if not family_parm:
                        # must be a broken instance
                        continue

                    family = family_parm.eval()
                    cache_legacy.setdefault(family, []).append(node)

            shared_data["houdini_cached_instances"] = cache
            shared_data["houdini_cached_legacy_instance"] = cache_legacy

        return shared_data

    @staticmethod
    def create_instance_node(
        folder_path,
        node_name,
        parent,
        node_type="geometry",
        pre_create_data=None,
        instance_data=None
    ):
        """Create node representing instance.

        Arguments:
            folder_path (str): Folder path.
            node_name (str): Name of the new node.
            parent (str): Name of the parent node.
            node_type (str, optional): Type of the node.
            pre_create_data (Optional[Dict]): Pre create data.
            instance_data (Optional[Dict]): Instance data.

        Returns:
            hou.Node: Newly created instance node.

        """
        parent_node = hou.node(parent)
        instance_node = parent_node.createNode(
            node_type, node_name=node_name)
        instance_node.moveToGoodPosition()
        return instance_node


class HoudiniCreator(Creator, HoudiniCreatorBase):
    """Base class for most of the Houdini creator plugins."""
    selected_nodes = []
    settings_name = None
    add_publish_button = False
    default_staging_dir = "$HIP/ayon"
    enable_staging_path_management = True

    settings_category = SETTINGS_CATEGORY

    def create(self, product_name, instance_data, pre_create_data):
        try:
            self.selected_nodes = []

            if pre_create_data.get("use_selection"):
                self.selected_nodes = hou.selectedNodes()

            # Get the node type and remove it from the data, not needed
            node_type = instance_data.pop("node_type", None)
            if node_type is None:
                node_type = "geometry"

            folder_path = instance_data["folderPath"]

            instance_node = self.create_instance_node(
                folder_path,
                product_name,
                "/out",
                node_type,
                pre_create_data,
                instance_data=instance_data
            )

            self.customize_node_look(instance_node)

            instance_data["instance_node"] = instance_node.path()
            instance_data["instance_id"] = instance_node.path()
            instance_data["families"] = self.get_publish_families()
            instance = CreatedInstance(
                self.product_type,
                product_name,
                instance_data,
                self)

            if self.enable_staging_path_management:
                staging_dir_info = self.get_staging_dir(instance)
                staging_dir = staging_dir_info.directory

                if self.expand_staging_dir:
                    with hou.ScriptEvalContext(instance_node):
                        # Expand vars only without expanding expressions
                        #   to keep dynamic link to ROP parameters.
                        staging_dir = expand_houdini_string(staging_dir)

                self.set_node_staging_dir(
                    instance_node,
                    staging_dir,
                    instance,
                    pre_create_data
                )

            self._add_instance_to_context(instance)
            self.imprint(instance_node, instance.data_to_store())

            if self.add_publish_button:
                add_self_publish_button(instance_node)

            return instance

        except hou.Error as exc:
            raise CreatorError(f"Creator error: {exc}") from exc

    def lock_parameters(self, node, parameters):
        """Lock list of specified parameters on the node.

        Args:
            node (hou.Node): Houdini node to lock parameters on.
            parameters (list of str): List of parameter names.

        """
        for name in parameters:
            try:
                parm = node.parm(name)
                parm.lock(True)
            except AttributeError:
                self.log.debug("missing lock pattern {}".format(name))

    def collect_instances(self):
        # cache instances  if missing
        self.cache_instance_data(self.collection_shared_data)
        for instance in self.collection_shared_data[
                "houdini_cached_instances"].get(self.identifier, []):

            node_data = read(instance)

            # Node paths are always the full node path since that is unique
            # Because it's the node's path it's not written into attributes
            # but explicitly collected
            node_path = instance.path()
            node_data["instance_id"] = node_path
            node_data["instance_node"] = node_path
            node_data["families"] = self.get_publish_families()
            if "AYON_productName" in node_data:
                node_data["productName"] = node_data.pop("AYON_productName")

            created_instance = CreatedInstance.from_existing(
                node_data, self
            )
            self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = hou.node(created_inst.get("instance_node"))
            new_values = {
                key: changes[key].new_value
                for key in changes.changed_keys
            }
            # Update parm templates and values
            self.imprint(
                instance_node,
                new_values,
                update=True
            )

    def imprint(self, node, values, update=False):
        # Never store instance node and instance id since that data comes
        # from the node's path
        if "productName" in values:
            values["AYON_productName"] = values.pop("productName")
        values.pop("instance_node", None)
        values.pop("instance_id", None)
        values.pop("families", None)
        imprint(node, values, update=update)

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        This is only removing `id` parameter so instance is no longer
        instance, because it might contain valuable data for artist.

        """
        for instance in instances:
            instance_node = hou.node(instance.data.get("instance_node"))
            if instance_node:
                instance_node.destroy()

            self._remove_instance_from_context(instance)

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("use_selection", default=True, label="Use selection")
        ]

    @staticmethod
    def customize_node_look(
            node, color=None,
            shape="chevron_down"):
        """Set custom look for instance nodes.

        Args:
            node (hou.Node): Node to set look.
            color (hou.Color, Optional): Color of the node.
            shape (str, Optional): Shape name of the node.

        Returns:
            None

        """
        if not color:
            color = hou.Color((0.616, 0.871, 0.769))
        node.setUserData('nodeshape', shape)
        node.setColor(color)

    def get_publish_families(self):
        """Return families for the instances of this creator.

        Allow a Creator to define multiple families so that a creator can
        e.g. specify `usd` and `usdrop`.

        There is no need to override this method if you only have the
        primary family defined by the `product_type` property as that will
        always be set.

        Returns:
            List[str]: families for instances of this creator
        """
        return []

    def get_network_categories(self):
        """Return in which network view type this creator should show.

        The node type categories returned here will be used to define where
        the creator will show up in the TAB search for nodes in Houdini's
        Network View.

        This can be overridden in inherited classes to define where that
        particular Creator should be visible in the TAB search.

        Returns:
            list: List of houdini node type categories

        """
        return [hou.ropNodeTypeCategory()]

    def apply_settings(self, project_settings):
        """Method called on initialization of plugin to apply settings."""

        # Apply General Settings
        houdini_general_settings = project_settings["houdini"]["general"]
        self.add_publish_button = houdini_general_settings.get(
            "add_self_publish_button", False)

        set_rop_output = houdini_general_settings["set_rop_output"]
        self.enable_staging_path_management = set_rop_output["enabled"]
        self.expand_staging_dir = set_rop_output["expand_vars"]
        self.default_staging_dir = \
            set_rop_output["default_output_dir"] or self.default_staging_dir

        # Apply Creator Settings
        settings_name = self.settings_name
        if settings_name is None:
            settings_name = self.__class__.__name__

        settings = project_settings["houdini"]["create"]
        settings = settings.get(settings_name)
        if settings is None:
            self.log.debug(
                "No settings found for {}".format(self.__class__.__name__)
            )
            return

        for key, value in settings.items():
            setattr(self, key, value)

    def get_staging_dir(self, instance) -> Optional[StagingDir]:
        """Get Staging Dir

        Return the staging dir and persistence from instance.

        This method falls back to the default output path defined in settings
        `ayon+settings://houdini/general/rop_output/default_output_dir`

        Args:
            instance (CreatedInstance): Instance for which should be staging
                dir gathered.

        Returns:
            Optional[StagingDir]: Staging dir path
        """

        staging_dir_info = super().get_staging_dir(instance)

        if staging_dir_info is None:
            staging_dir_info = StagingDir(
                self.default_staging_dir,
                is_persistent=False,
                is_custom=True,
            )

        staging_dir_info.directory = (
            staging_dir_info.directory
            .replace("\\", "/")
            .rstrip("/")
        )

        return staging_dir_info

    def set_node_staging_dir(
            self, node: hou.Node,
            staging_dir: str,
            instance: CreatedInstance,
            pre_create_data: dict
    ):
        """Set Node Staging Dir

        Args:
            node (hou.Node): Houdini node to set its output directory.
            staging_dir (str): Staging output directory.
            instance (CreatedInstance): Instance object associated
                with the given node.
            pre_create_data(dict): Data based on pre creation attributes.

        """

        raise NotImplementedError(
            f"{self.__class__.__name__} "
            "doesn't implement `set_node_staging_dir`"
        )


class RenderLegacyProductTypeCreator(HoudiniCreator):
    """Creator for Render ROPs to allow toggling between legacy product types
    and the 'render' product type. This is mostly for backwards
    compatibility. See #214."""

    # Overriding `product_type` avoids linters complaining that the attribute
    # is actually a property that can't be assigned to in `apply_settings`
    # because it inherits as property from `Creator`.
    product_type = "render"
    legacy_product_type = "render"
    use_legacy_product_type = False

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)
        use_legacy_product_type = project_settings["houdini"]["create"].get(
            "render_rops_use_legacy_product_type", False
        )
        if use_legacy_product_type:
            self.product_type = self.legacy_product_type


class HoudiniLoader(load.LoaderPlugin):
    """Base class for Houdini load plugins."""

    hosts = ["houdini"]
    settings_category = SETTINGS_CATEGORY
    use_ayon_entity_uri = False
    collapse_paths_to_root_vars = False

    @classmethod
    def apply_settings(cls, project_settings):
        # Prepare collapsible variable mapping using entries in `os.environ`
        # that are set to the project root paths
        cls.collapse_paths_to_root_vars: bool = (
            project_settings["houdini"]["load"]
            .get("collapse_path_to_project_root_vars", False)
        )

        super().apply_settings(project_settings)

    @classmethod
    def _get_collapsible_vars(cls) -> Dict[str, str]:
        """Return which variables keys may be collapsed to if path starts with
        the values."""
        collapsible_vars = {}
        for key, value in os.environ.items():
            if key.startswith("AYON_PROJECT_ROOT_"):
                if not value:
                    continue
                collapsible_vars[key] = value.replace("\\", "/")

        # Sort by length to ensure that the longest matching key is first
        # so that the nearest matching root is used
        return {
            key: value
            for key, value
            in sorted(collapsible_vars.items(),
                      key=lambda x: len(x[1]),
                      reverse=True)
        }

    @classmethod
    def filepath_from_context(cls, context):
        if cls.use_ayon_entity_uri:
            return get_ayon_entity_uri_from_representation_context(context)

        path = super().filepath_from_context(context)

        # Remap project roots to the collapsible path variables
        if cls.collapse_paths_to_root_vars:
            collapsible_vars = cls._get_collapsible_vars()
            if collapsible_vars:
                match_path = path.replace("\\", "/")
                for key, value in collapsible_vars.items():
                    if match_path.startswith(value):
                        # Replace start of string with the key
                        path = f"${key}" + path[len(value):]
                        break

        return path


class HoudiniInstancePlugin(pyblish.api.InstancePlugin):
    """Base class for Houdini instance publish plugins."""

    hosts = ["houdini"]
    settings_category = SETTINGS_CATEGORY


class HoudiniContextPlugin(pyblish.api.ContextPlugin):
    """Base class for Houdini context publish plugins."""

    hosts = ["houdini"]
    settings_category = SETTINGS_CATEGORY


class HoudiniExtractorPlugin(publish.Extractor):
    """Base class for Houdini extract plugins.

    Note:
        The `HoudiniExtractorPlugin` is a subclass of `publish.Extractor`,
            which in turn is a subclass of `pyblish.api.InstancePlugin`.
        Should there be a requirement to create an extractor that operates
            as a context plugin, it would be beneficial to incorporate
            the functionalities present in `publish.Extractor`.
    """

    hosts = ["houdini"]
    settings_category = SETTINGS_CATEGORY

    def render_rop(self, instance: pyblish.api.Instance):
        """Render the ROP node of the instance.

        If `instance.data["frames_to_fix"]` is set and is not empty it will
        be interpreted as a set of frames that will be rendered instead of the
        full rop nodes frame range.

        Only `instance.data["instance_node"]` is required.
        """
        # Log the start of the render
        rop_node = hou.node(instance.data["instance_node"])
        self.log.debug(f"Rendering {rop_node.path()}")

        frames_to_fix = clique.parse(instance.data.get("frames_to_fix", ""),
                                     "{ranges}")
        if len(set(frames_to_fix)) < 2:
            render_rop(rop_node)
            return

        # Render only frames to fix
        for frame_range in frames_to_fix.separate():
            frame_range = list(frame_range)
            first_frame = int(frame_range[0])
            last_frame = int(frame_range[-1])
            self.log.debug(
                f"Rendering frames to fix [{first_frame}, {last_frame}]"
            )
            # for step to be 1 since clique doesn't support steps.
            frame_range = (first_frame, last_frame, 1)
            render_rop(rop_node, frame_range=frame_range)
