"""Heper functions for load HDA"""

import os
import re
import uuid
from typing import List

import hou
from qtpy import QtCore, QtWidgets, QtGui

import ayon_api
from ayon_api import (
    get_project,
    get_representation_by_id,
    get_versions,
    get_folder_by_path,
    get_product_by_name,
    get_version_by_name,
    get_representation_by_name,
    get_representations
)
from ayon_core.pipeline import Anatomy
from ayon_core.lib import StringTemplate
from ayon_core.pipeline.context_tools import (
    get_current_project_name,
    get_current_folder_path
)
from ayon_core.pipeline.load import (
    get_representation_context,
    get_representation_path_from_context
)
from ayon_core.style import load_stylesheet
from ayon_core.tools.utils import SimpleFoldersWidget
from ayon_houdini.api import lib
from .usd import get_ayon_entity_uri_from_representation_context


def get_session_cache() -> dict:
    """Get a persistent `hou.session.ayon_cache` dict"""
    cache = getattr(hou.session, "ayon_cache", None)
    if cache is None:
        hou.session.ayon_cache = cache = {}
    return cache


def is_valid_uuid(value) -> bool:
    """Return whether value is a valid UUID"""
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def get_available_versions(node):
    """Return the versions list for node.

    The versions are sorted with the latest version first and oldest lower
    version last.

    Args:
        node (hou.Node): Node to query selected products' versions for.

    Returns:
        list[int]: Version numbers for the product
    """

    project_name = node.evalParm("project_name") or get_current_project_name()
    folder_path = node.evalParm("folder_path")
    product_name = node.evalParm("product_name")

    if not all([
        project_name, folder_path, product_name
    ]):
        return []

    folder_entity = get_folder_by_path(
        project_name,
        folder_path,
        fields={"id"})
    if not folder_entity:
        return []
    product_entity = get_product_by_name(
        project_name,
        product_name=product_name,
        folder_id=folder_entity["id"],
        fields={"id"})
    if not product_entity:
        return []

    # TODO: Support hero versions
    versions = get_versions(
        project_name,
        product_ids={product_entity["id"]},
        fields={"version"},
        hero=False)
    version_names = [version["version"] for version in versions]
    version_names.reverse()
    return version_names


def set_node_representation_from_context(
        node,
        context,
        ensure_expression_defaults=True
):
    """Update project, folder, product, version, representation name parms.

     Arguments:
         node (hou.Node): Node to update
         context (dict): Context of representation
         ensure_expression_defaults (bool): Ensure expression defaults.

     """
    # TODO: Avoid 'duplicate' taking over the expression if originally
    #       it was $OS and by duplicating, e.g. the `folder` does not exist
    #       anymore since it is now `hero1` instead of `hero`
    # TODO: Support hero versions
    version = str(context["version"]["version"])

    # We only set the values if the value does not match the currently
    # evaluated result of the other parms, so that if the project name
    # value was dynamically set by the user with an expression or alike
    # then if it still matches the value of the current representation id
    # we preserve it. In essence, only update the value if the current
    # *evaluated* value of the parm differs.
    parms = {
        "project_name": context["project"]["name"],
        "folder_path": context["folder"]["path"],
        "product_name": context["product"]["name"],
        "version": version,
        "representation_name": context["representation"]["name"],
    }
    parms = {key: value for key, value in parms.items()
             if node.evalParm(key) != value}
    node.setParms(parms)

    if ensure_expression_defaults:
        ensure_loader_expression_parm_defaults(node)


def ensure_loader_expression_parm_defaults(node):
    """Reset `representation` and `file` parm to defaults.

    The filepath and representation id parms are updated through expressions,
    however in older versions they were explicitly set so we ensure that the
    current value is set to the default value with the expression - otherwise
    the value will be set to the previously explicitly set overridden value.

    Silently ignores if the parm does not exist or is already at default.

    Args:
        node (hou.OpNode): The node to reset.

    """
    for parm_name in ["representation", "file"]:
        parm = node.parm(parm_name)
        if parm is None:
            continue

        # TODO: For whatever reason this still returns True even if the
        #  expression does not match the default, so for now we always revert
        # if parm.isAtDefault(compare_expressions=True):
        #     continue

        default_expression = parm.parmTemplate().defaultExpression()
        if not default_expression:
            continue

        default_expression = default_expression[0]

        try:
            current_expression = parm.expression()
            if current_expression == default_expression:
                continue
        except hou.OperationFailed:
            pass

        print(f"Enforcing {parm.path()} to default value")
        locked = parm.isLocked()
        parm.lock(False)
        parm.deleteAllKeyframes()
        parm.revertToDefaults()
        parm.lock(locked)


def get_representation_path(
    project_name: str,
    representation_id: str,
    use_ayon_entity_uri: bool
) -> str:
    # Ignore invalid representation ids silently
    # TODO remove - added for backwards compatibility with OpenPype scenes
    if not is_valid_uuid(representation_id):
        return ""

    repre_entity = get_representation_by_id(project_name, representation_id)
    if not repre_entity:
        return ""

    context = get_representation_context(project_name, repre_entity)
    if use_ayon_entity_uri:
        path = get_ayon_entity_uri_from_representation_context(context)
    else:
        path = _get_filepath_from_context(context)
        # Load fails on UNC paths with backslashes and also
        # fails to resolve @sourcename var with backslashed
        # paths correctly. So we force forward slashes
        path = path.replace("\\", "/")
    return path


def _remove_format_spec(template: str, key: str) -> str:
    """Remove format specifier from a format token in formatting string.
    For example, change `{frame:0>4d}` into `{frame}`
    Examples:
        >>> remove_format_spec("{frame:0>4d}", "frame")
        '{frame}'
        >>> remove_format_spec("{digit:04d}/{frame:0>4d}", "frame")
        '{digit:04d}/{udim}_{frame}'
        >>> remove_format_spec("{a: >4}/{aa: >4}", "a")
        '{a}/{aa: >4}'
    """
    # Find all {key:foobar} and remove the `:foobar`
    # Pattern will be like `({key):[^}]+(})` where we use the captured groups
    # to keep those parts in the resulting string
    pattern = f"({{{key}):[^}}]+(}})"
    return re.sub(pattern, r"\1\2", template)


def _get_filepath_from_context(context: dict):
    """Format file path for sequence with $F or <UDIM>."""
    # The path is either a single file or sequence in a folder.
    # Format frame as $F and udim as <UDIM>
    representation = context["representation"]
    frame = representation["context"].get("frame")
    udim = representation["context"].get("udim")
    if frame is not None or udim is not None:
        template: str = representation["attrib"]["template"]
        repre_context: dict = representation["context"]
        if udim is not None:
            repre_context["udim"] = "<UDIM>"
            template = _remove_format_spec(template, "udim")
        if frame is not None:
            # Substitute frame number in sequence with $F with padding
            repre_context["frame"] = "$F{}".format(len(frame))  # e.g. $F4
            template = _remove_format_spec(template, "frame")

        project_name: str = repre_context["project"]["name"]
        anatomy = Anatomy(project_name, project_entity=context["project"])
        repre_context["root"] = anatomy.roots
        path = StringTemplate(template).format(repre_context)
    else:
        path = get_representation_path_from_context(context)

    # Load fails on UNC paths with backslashes and also
    # fails to resolve @sourcename var with backslashed
    # paths correctly. So we force forward slashes
    return os.path.normpath(path).replace("\\", "/")


def _get_thumbnail(project_name: str, version_id: str, thumbnail_dir: str):
    folder = hou.text.expandString(thumbnail_dir)
    path = os.path.join(folder, "{}_thumbnail.jpg".format(version_id))
    expanded_path = hou.text.expandString(path)
    if os.path.isfile(expanded_path):
        return path

    # Try and create a thumbnail cache file
    data = ayon_api.get_thumbnail(project_name,
                                  entity_type="version",
                                  entity_id=version_id)
    if data:
        thumbnail_dir_expanded = hou.text.expandString(thumbnail_dir)
        os.makedirs(thumbnail_dir_expanded, exist_ok=True)
        with open(expanded_path, "wb") as f:
            f.write(data.content)
        return path


def update_thumbnail(node):
    if not node.evalParm("show_thumbnail"):
        lib.remove_all_thumbnails(node)
        return

    representation_id = node.evalParm("representation")
    if not representation_id:
        set_node_thumbnail(node, None)
        return

    project_name = (
        node.evalParm("project_name")
        or get_current_project_name()
    )
    repre_entity = get_representation_by_id(project_name, representation_id)
    if node.evalParm("show_thumbnail"):
        # Update thumbnail
        # TODO: Cache thumbnail path as well
        version_id = repre_entity["versionId"]
        thumbnail_dir = node.evalParm("thumbnail_cache_dir")
        thumbnail_path = _get_thumbnail(
            project_name, version_id, thumbnail_dir
        )
        set_node_thumbnail(node, thumbnail_path)


def set_node_thumbnail(node, thumbnail: str):
    """Update node thumbnail to thumbnail"""
    if thumbnail is None:
        lib.set_node_thumbnail(node, None)

    rect = compute_thumbnail_rect(node)
    lib.set_node_thumbnail(node, thumbnail, rect)


def compute_thumbnail_rect(node):
    """Compute thumbnail bounding rect based on thumbnail parms"""
    offset_x = node.evalParm("thumbnail_offsetx")
    offset_y = node.evalParm("thumbnail_offsety")
    width = node.evalParm("thumbnail_size")
    # todo: compute height from aspect of actual image file.
    aspect = 0.5625  # for now assume 16:9
    height = width * aspect

    center = 0.5
    half_width = (width * .5)

    return hou.BoundingRect(
        offset_x + center - half_width,
        offset_y,
        offset_x + center + half_width,
        offset_y + height
    )


def on_thumbnail_show_changed(node):
    """Callback on thumbnail show parm changed"""
    update_thumbnail(node)


def on_thumbnail_size_changed(node):
    """Callback on thumbnail offset or size parms changed"""
    thumbnail = lib.get_node_thumbnail(node)
    if thumbnail:
        rect = compute_thumbnail_rect(node)
        thumbnail.setRect(rect)
        lib.set_node_thumbnail(node, thumbnail)


def get_node_expected_representation_id(node) -> str:
    project_name = node.evalParm(
        "project_name") or get_current_project_name()
    return get_representation_id(
            project_name=project_name,
            folder_path=node.evalParm("folder_path"),
            product_name=node.evalParm("product_name"),
            version=node.evalParm("version"),
            representation_name=node.evalParm("representation_name"),
    )


def get_representation_id(
        project_name,
        folder_path,
        product_name,
        version,
        representation_name,
):
    """Get representation id.

    Args:
        project_name (str): Project name
        folder_path (str): Folder name
        product_name (str): Product name
        version (str): Version name as string
        representation_name (str): Representation name

    Returns:
        str: Representation id or None if not found.

    Raises:
        ValueError: If the entity could not be resolved with input values.

    """
    if not all([
        project_name, folder_path, product_name, version, representation_name
    ]):
        labels = {
            "project": project_name,
            "folder": folder_path,
            "product": product_name,
            "version": version,
            "representation": representation_name
        }
        missing = ", ".join(key for key, value in labels.items() if not value)
        raise ValueError(f"Load info incomplete. Found empty: {missing}")

    try:
        version = int(version.strip())
    except ValueError:
        raise ValueError(
            f"Invalid version format: '{version}'\n"
            "Make sure to set a valid version number.")

    folder_entity = get_folder_by_path(project_name,
                                       folder_path=folder_path,
                                       fields={"id"})
    if not folder_entity:
        # This may be due to the project not existing - so let's validate
        # that first
        if not get_project(project_name):
            raise ValueError(f"Project not found: '{project_name}'")
        raise ValueError(f"Folder not found: '{folder_path}'")

    product_entity = get_product_by_name(
        project_name,
        product_name=product_name,
        folder_id=folder_entity["id"],
        fields={"id"})
    if not product_entity:
        raise ValueError(f"Product not found: '{product_name}'")

    version_entity = get_version_by_name(
        project_name,
        version,
        product_id=product_entity["id"],
        fields={"id"})
    if not version_entity:
        raise ValueError(f"Version not found: '{version}'")

    representation_entity = get_representation_by_name(
        project_name,
        representation_name,
        version_id=version_entity["id"],
        fields={"id"})
    if not representation_entity:
        raise ValueError(f"Representation not found: '{representation_name}'.")
    return representation_entity["id"]


def setup_flag_changed_callback(node):
    """Register flag changed callback (for thumbnail brightness)"""
    node.addEventCallback(
        (hou.nodeEventType.FlagChanged,),
        on_flag_changed
    )


def on_flag_changed(node, **kwargs):
    """On node flag changed callback.

    Updates the brightness of attached thumbnails
    """
    # Showing thumbnail is disabled so can return early since
    # there should be no thumbnail to update.
    if not node.evalParm('show_thumbnail'):
        return

    # Update node thumbnails brightness with the
    # bypass state of the node.
    parent = node.parent()
    images = lib.get_background_images(parent)
    if not images:
        return

    # This may trigger on a node that can't be bypassed, like `ObjNode` so
    # consider those never bypassed
    is_bypassed = hasattr(node, "isBypassed") and node.isBypassed()
    brightness = 0.3 if is_bypassed else 1.0
    has_changes = False
    node_path = node.path()
    for image in images:
        if image.relativeToPath() == node_path:
            image.setBrightness(brightness)
            has_changes = True

    if has_changes:
        lib.set_background_images(parent, images)


def keep_background_images_linked(node, old_name):
    """Reconnect background images to node from old name.

     Used as callback on node name changes to keep thumbnails linked."""
    from ayon_houdini.api.lib import (
        get_background_images,
        set_background_images
    )

    parent = node.parent()
    images = get_background_images(parent)
    if not images:
        return

    changes = False
    old_path = f"{node.parent().path()}/{old_name}"
    for image in images:
        if image.relativeToPath() == old_path:
            image.setRelativeToPath(node.path())
            changes = True

    if changes:
        set_background_images(parent, images)


class SelectFolderPathDialog(QtWidgets.QDialog):
    """Simple dialog to allow a user to select project and asset."""

    def __init__(self, parent=None):
        super(SelectFolderPathDialog, self).__init__(parent)
        self.setWindowTitle("Set project and folder path")
        self.setStyleSheet(load_stylesheet())

        project_widget = QtWidgets.QComboBox()
        project_widget.addItems(self.get_projects())

        filter_widget = QtWidgets.QLineEdit()
        filter_widget.setPlaceholderText("Folder name filter...")

        folder_widget = SimpleFoldersWidget(parent=self)

        accept_button = QtWidgets.QPushButton("Set folder path")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(project_widget, 0)
        main_layout.addWidget(filter_widget, 0)
        main_layout.addWidget(folder_widget, 1)
        main_layout.addWidget(accept_button, 0)

        self.project_widget = project_widget
        self.folder_widget = folder_widget

        project_widget.currentTextChanged.connect(self.on_project_changed)
        filter_widget.textChanged.connect(folder_widget.set_name_filter)
        folder_widget.double_clicked.connect(self.accept)
        accept_button.clicked.connect(self.accept)

    def get_selected_folder_path(self) -> str:
        return self.folder_widget.get_selected_folder_path()

    def get_selected_project_name(self) -> str:
        return self.project_widget.currentText()

    def get_projects(self) -> List[str]:
        projects = ayon_api.get_projects(fields=["name"])
        return [p["name"] for p in projects]

    def on_project_changed(self, project_name: str):
        self.folder_widget.set_project_name(project_name)

    def set_project_name(self, project_name: str):
        self.project_widget.setCurrentText(project_name)

        if self.project_widget.currentText() != project_name:
            # Project does not exist
            return

        # Force the set of widget because even though a callback exist on the
        # project widget it may have been initialized to that value and hence
        # detect no change.
        self.folder_widget.set_project_name(project_name)


def select_folder_path(node):
    """Show dialog to select folder path.

    When triggered it opens a dialog that shows the available
    folder paths within a given project.

    Note:
        This function should be refactored.
        It currently shows the available
          folder paths within the current project only.

    Args:
        node (hou.OpNode): The HDA node.
    """
    cursor_pos = QtGui.QCursor.pos()

    main_window = lib.get_main_window()

    project_name = node.evalParm("project_name")
    folder_path = node.evalParm("folder_path")

    dialog = SelectFolderPathDialog(parent=main_window)
    dialog.set_project_name(project_name)
    if folder_path:
        # We add a small delay to the setting of the selected folder
        # because the folder widget's set project logic itself also runs
        # with a bit of a delay, and unfortunately otherwise the project
        # has not been selected yet and thus selection does not work.
        def _select_folder_path():
            dialog.folder_widget.set_selected_folder_path(folder_path)
        QtCore.QTimer.singleShot(100, _select_folder_path)

    dialog.setStyleSheet(load_stylesheet())

    # Make it appear like a pop-up near cursor
    dialog.resize(300, 600)
    dialog.setWindowFlags(QtCore.Qt.Popup)
    pos = dialog.mapToGlobal(cursor_pos - QtCore.QPoint(300, 0))
    dialog.move(pos)

    result = dialog.exec_()
    if result != QtWidgets.QDialog.Accepted:
        return

    # Set project
    selected_project_name = dialog.get_selected_project_name()
    if selected_project_name == get_current_project_name():
        selected_project_name = '$AYON_PROJECT_NAME'

    project_parm = node.parm("project_name")
    project_parm.set(selected_project_name)
    project_parm.pressButton()  # allow any callbacks to trigger

    # Set folder path
    selected_folder_path = dialog.get_selected_folder_path()
    if not selected_folder_path:
        # Do nothing if user accepted with nothing selected
        return

    if selected_folder_path == get_current_folder_path():
        selected_folder_path = '$AYON_FOLDER_PATH'

    folder_parm = node.parm("folder_path")
    folder_parm.set(selected_folder_path)
    folder_parm.pressButton()  # allow any callbacks to trigger


class SelectProductDialog(QtWidgets.QDialog):
    """Simple dialog to allow a user to select a product."""

    def __init__(self, project_name, folder_id, parent=None):
        super(SelectProductDialog, self).__init__(parent)
        self.setWindowTitle("Select a Product")
        self.setStyleSheet(load_stylesheet())

        self.project_name = project_name
        self.folder_id = folder_id

        # Create widgets and layout
        product_types_widget = QtWidgets.QComboBox()
        products_widget = QtWidgets.QListWidget()
        accept_button = QtWidgets.QPushButton("Set product name")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(product_types_widget, 0)
        main_layout.addWidget(products_widget, 1)
        main_layout.addWidget(accept_button, 0)

        self.product_types_widget = product_types_widget
        self.products_widget = products_widget

        # Connect Signals
        product_types_widget.currentTextChanged.connect(self.on_product_type_changed)
        products_widget.itemDoubleClicked.connect(self.accept)
        accept_button.clicked.connect(self.accept)

        # Initialize widgets contents
        product_types_widget.addItems(self.get_product_types())
        product_type = self.get_selected_product_type()
        self.set_product_type(product_type)

    def get_selected_product(self) -> str:
        if self.products_widget.currentItem():
            return self.products_widget.currentItem().text()
        return ""

    def get_selected_product_type(self) -> str:
        return self.product_types_widget.currentText()

    def get_product_types(self) -> List[str]:
        """return default product types.
        """

        return [
            "*",
            "animation",
            "camera",
            "model",
            "pointcache",
            "usd",
        ]

    def on_product_type_changed(self, product_type: str):  
        self.set_product_type(product_type)

    def set_product_type(self, product_type: str):
        self.product_types_widget.setCurrentText(product_type)

        if self.product_types_widget.currentText() != product_type:
            # Product type does not exist
            return

        # Populate products list
        products = self.get_available_products(product_type)
        self.products_widget.clear()
        if products:
            self.products_widget.addItems(products)

    def set_selected_product_name(self, product_name: str):
        matching_items = self.products_widget.findItems(
            product_name, QtCore.Qt.MatchFixedString)
        if matching_items:
            self.products_widget.setCurrentItem(matching_items[0])

    def get_available_products(self, product_type):
        
        if product_type == "*":
            product_type = ""

        product_types = [product_type] if product_type else None

        products = ayon_api.get_products(
            self.project_name,
            folder_ids=[self.folder_id],
            product_types=product_types
        )

        return list(sorted(product["name"] for product in products))


def select_product_name(node):
    """Show a modal pop-up dialog to allow user to select a product name
    under the current folder entity as defined on the node's parameters.

    Applies the chosen value to the `product_name` parm on the node."""

    cursor_pos = QtGui.QCursor.pos()

    project_name = node.evalParm("project_name")
    folder_path = node.evalParm("folder_path")
    product_parm = node.parm("product_name")

    folder_entity = ayon_api.get_folder_by_path(project_name,
                                                folder_path,
                                                fields={"id"})
    if not folder_entity:
        return
          
    dialog = SelectProductDialog(
        project_name,
        folder_entity["id"],
        parent=lib.get_main_window() 
    )
    dialog.set_selected_product_name(product_parm.eval())

    dialog.resize(300, 600)
    dialog.setWindowFlags(QtCore.Qt.Popup)
    pos = dialog.mapToGlobal(cursor_pos - QtCore.QPoint(300, 0))
    dialog.move(pos)
    result = dialog.exec_()

    if result != QtWidgets.QDialog.Accepted:
        return
    selected_product = dialog.get_selected_product()

    if selected_product:
        product_parm.set(selected_product)
        product_parm.pressButton()  # allow any callbacks to trigger


def get_available_representations(node):
    """Return the representation list for node.

    Args:
        node (hou.Node): Node to query selected version's representations for.

    Returns:
        list[str]: representation names for the product version.
    """

    project_name = node.evalParm("project_name") or get_current_project_name()
    folder_path = node.evalParm("folder_path")
    product_name = node.evalParm("product_name")
    version = node.evalParm("version")

    if not all([
        project_name, folder_path, product_name, version
    ]):
        return []

    try:
        version = int(version.strip())
    except ValueError:
        load_message_parm = node.parm("load_message")
        load_message_parm.set(f"Invalid version format: '{version}'\n"
                              "Make sure to set a valid version number.")
        return

    folder_entity = get_folder_by_path(
        project_name,
        folder_path=folder_path,
        fields={"id"}
    )
    product_entity = get_product_by_name(
            project_name,
            product_name=product_name,
            folder_id=folder_entity["id"],
            fields={"id"})
    version_entity = get_version_by_name(
            project_name,
            version,
            product_id=product_entity["id"],
            fields={"id"})
    representations = get_representations(
            project_name,
            version_ids={version_entity["id"]},
            fields={"name"}
    )
    representations_names = [n["name"] for n in representations]
    return representations_names


def set_to_latest_version(node):
    """Callback on product name change

    Refresh version and representation parameters value by setting
    their value to the latest version and representation of
    the selected product.

    Args:
        node (hou.OpNode): The HDA node.
    """

    versions = get_available_versions(node)
    if versions:
        node.parm("version").set(str(versions[0]))

    representations = get_available_representations(node)
    if representations:
        node.parm("representation_name").set(representations[0])


# region Parm Expressions
# Callbacks used for expression on HDAs (e.g. Load Asset or Load Shot LOP)
# Note that these are called many times, sometimes even multiple times when
# the Parameters tab is open on the node. So some caching is performed to
# avoid expensive re-querying.
def expression_clear_cache(subkey=None) -> bool:
    # Clear full cache if no subkey provided
    if subkey is None:
        if hasattr(hou.session, "ayon_cache"):
            delattr(hou.session, "ayon_cache")
            return True
        return False

    # Clear only key in cache if provided
    cache = getattr(hou.session, "ayon_cache", {})
    if subkey in cache:
        cache.pop(subkey)
        return True
    return False


def expression_get_representation_id() -> str:
    project_name = hou.evalParm("project_name")
    folder_path = hou.evalParm("folder_path")
    product_name = hou.evalParm("product_name")
    version = hou.evalParm("version")
    representation_name = hou.evalParm("representation_name")

    node = hou.pwd()
    hash_value = (project_name, folder_path, product_name, version,
                  representation_name)
    cache = get_session_cache().setdefault("representation_ids", {})
    if hash_value in cache:
        return cache[hash_value]

    try:
        repre_id = get_node_expected_representation_id(node)
    except ValueError:
        # Ignore invalid parameters
        repre_id = ""

    cache[hash_value] = repre_id
    return repre_id


def expression_get_representation_path() -> str:
    cache = get_session_cache().setdefault("representation_path", {})
    project_name: str = hou.evalParm("project_name")
    repre_id: str = hou.evalParm("representation")
    use_entity_uri = bool(hou.evalParm("use_ayon_entity_uri"))
    hash_value = project_name, repre_id, use_entity_uri
    if hash_value in cache:
        return cache[hash_value]

    path = get_representation_path(project_name, repre_id, use_entity_uri)
    cache[hash_value] = path
    return path

# endregion

