from qtpy import QtWidgets, QtCore, QtGui
import ayon_api

from ayon_core.style import load_stylesheet

from ayon_core.pipeline.context_tools import (
    get_current_project_name,
    get_current_folder_path
)

from ayon_houdini.api.hda_utils import (
    SelectFolderPathDialog,
    SelectProductDialog
)

def get_available_versions(project_name, folder_path, product_name):
    """Return the versions list for node.

    The versions are sorted with the latest version first and oldest lower
    version last.

    Args:
        node (hou.Node): Node to query selected products' versions for.

    Returns:
        list[int]: Version numbers for the product
    """

    if not all([
        project_name, folder_path, product_name
    ]):
        return []

    folder_entity = ayon_api.get_folder_by_path(
        project_name,
        folder_path,
        fields={"id"})
    if not folder_entity:
        return []
    product_entity = ayon_api.get_product_by_name(
        project_name,
        product_name=product_name,
        folder_id=folder_entity["id"],
        fields={"id"})
    if not product_entity:
        return []

    # TODO: Support hero versions
    versions = ayon_api.get_versions(
        project_name,
        product_ids={product_entity["id"]},
        fields={"version"},
        hero=False)
    version_names = [version["version"] for version in versions]
    version_names.reverse()
    return version_names


def get_available_representations(project_name, folder_path, product_name, version):
    """Return the representation list for node.

    Args:
        node (hou.Node): Node to query selected version's representations for.

    Returns:
        list[str]: representation names for the product version.
    """

    if not all([
        project_name, folder_path, product_name, version
    ]):
        return []

    folder_entity = ayon_api.get_folder_by_path(
        project_name,
        folder_path=folder_path,
        fields={"id"}
    )
    product_entity = ayon_api.get_product_by_name(
            project_name,
            product_name=product_name,
            folder_id=folder_entity["id"],
            fields={"id"})
    version_entity = ayon_api.get_version_by_name(
            project_name,
            version,
            product_id=product_entity["id"],
            fields={"id"})
    representations = ayon_api.get_representations(
            project_name,
            version_ids={version_entity["id"]},
            fields={"name"}
    )   
    representations_names = [n["name"] for n in representations]
    return representations_names


class SelectAYONProductDialog(QtWidgets.QDialog):
    """Basic dialog."""

    finished = QtCore.Signal(bool)

    def __init__(self, parent=None, node=None):
        super(SelectAYONProductDialog, self).__init__(parent)
        self.node = node

        self.setWindowTitle("Choose AYON Product")
        self.resize(300, 120)

        # Project
        widget_1 = QtWidgets.QWidget(self)
        label_1 = QtWidgets.QLabel("Project", self)
        self.project_name = QtWidgets.QLineEdit(get_current_project_name(), widget_1)
        project_folder_btn = QtWidgets.QPushButton("Project_folder")
        project_folder_btn.clicked.connect(self._select_project_folder)

        widget_1_layout = QtWidgets.QHBoxLayout(widget_1)
        widget_1_layout.addWidget(label_1)
        widget_1_layout.addWidget(self.project_name)
        widget_1_layout.addWidget(project_folder_btn)

        # Folder Path
        widget_2 = QtWidgets.QWidget(self)
        label_2 = QtWidgets.QLabel("Folder Path", self)
        self.folder_path = QtWidgets.QLineEdit(get_current_folder_path(), widget_2)

        widget_2_layout = QtWidgets.QHBoxLayout(widget_2)
        widget_2_layout.addWidget(label_2)
        widget_2_layout.addWidget(self.folder_path)
        widget_2_layout.addWidget(project_folder_btn)

        # Product
        widget_3 = QtWidgets.QWidget(self)
        label_3 = QtWidgets.QLabel("Product", self)
        self.product_name = QtWidgets.QLineEdit(self)
        product_btn = QtWidgets.QPushButton("Product")
        product_btn.clicked.connect(self._select_product)

        widget_3_layout = QtWidgets.QHBoxLayout(widget_3)
        widget_3_layout.addWidget(label_3)
        widget_3_layout.addWidget(self.product_name)
        widget_3_layout.addWidget(product_btn)

        # Version
        widget_4 = QtWidgets.QWidget(self)
        label_4 = QtWidgets.QLabel("Version", self)
        self.version = QtWidgets.QComboBox()
        self.version.currentTextChanged.connect(self._on_version_change)

        widget_4_layout = QtWidgets.QHBoxLayout(widget_4)
        widget_4_layout.addWidget(label_4)
        widget_4_layout.addWidget(self.version)

        # Representation
        widget_5 = QtWidgets.QWidget(self)
        label_5 = QtWidgets.QLabel("Representation", self)
        self.representation = QtWidgets.QComboBox()

        widget_5_layout = QtWidgets.QHBoxLayout(widget_5)
        widget_5_layout.addWidget(label_5)
        widget_5_layout.addWidget(self.representation)

        # Buttons
        buttons_widget = QtWidgets.QWidget(self)

        ok_btn = QtWidgets.QPushButton("Apply", buttons_widget)

        buttons_layout = QtWidgets.QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(ok_btn)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addSpacing(5)
        layout.addWidget(widget_1)
        layout.addWidget(widget_2)
        layout.addWidget(widget_3)
        layout.addWidget(widget_4)
        layout.addWidget(widget_5)
        layout.addStretch(1)
        layout.addWidget(buttons_widget, 0)

        ok_btn.clicked.connect(self._on_ok_click)

        self._final_result = None

        self.setStyleSheet(load_stylesheet())

    def result(self):
        return self._final_result

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._on_ok_click()
            return event.accept()
        super(SelectAYONProductDialog, self).keyPressEvent(event)

    def closeEvent(self, event):
        super(SelectAYONProductDialog, self).closeEvent(event)
        self.finished.emit(self.result())

    def _on_ok_click(self):
        self._final_result = {
            "project_name": self.project_name.text(),
            "folder_path": self.folder_path.text(),
            "product_name": self.product_name.text(),
            "version": self.version.currentText(),
            "representation_name": self.representation.currentText(),
        }
        if self.node: 
            self.node.setParms(self._final_result)

    def _select_project_folder(self):
        curr_project_name = get_current_project_name()
        curr_folder_path = get_current_folder_path()

        cursor_pos = QtGui.QCursor.pos()
        
        dialog = SelectFolderPathDialog(self)
        dialog.set_project_name(curr_project_name)
        if curr_folder_path:
            # We add a small delay to the setting of the selected folder
            # because the folder widget's set project logic itself also runs
            # with a bit of a delay, and unfortunately otherwise the project
            # has not been selected yet and thus selection does not work.
            def _select_folder_path():
                dialog.folder_widget.set_selected_folder_path(curr_folder_path)
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
        self.project_name.setText(selected_project_name)

        # Set folder path
        selected_folder_path = dialog.get_selected_folder_path()
        if not selected_folder_path:
            # Do nothing if user accepted with nothing selected
            return

        self.folder_path.setText(selected_folder_path)

    def _select_product(self):
        cursor_pos = QtGui.QCursor.pos()

        project_name = self.project_name.text()
        folder_path = self.folder_path.text()
        curr_product_name = self.product_name.text()
        
        folder_entity = ayon_api.get_folder_by_path(project_name,
                                                folder_path,
                                                fields={"id"})
        if not folder_entity:
            return
            
        dialog = SelectProductDialog(
            project_name,
            folder_entity["id"],
            parent=self
        )
        dialog.set_selected_product_name(curr_product_name)
        dialog.resize(300, 600)
        dialog.setWindowFlags(QtCore.Qt.Popup)
        pos = dialog.mapToGlobal(cursor_pos - QtCore.QPoint(300, 0))
        dialog.move(pos)
        result = dialog.exec_()

        if result != QtWidgets.QDialog.Accepted:
            return
        selected_product = dialog.get_selected_product()

        if not selected_product:
            return 
        self.product_name.setText(selected_product)

        # populate versions.
        versions = get_available_versions(project_name, folder_path, selected_product)
        versions = [str(v) for v in versions]

        self.version.clear()
        self.version.addItems(versions)
        self.version.setCurrentText(versions[0])

    def _on_version_change(self):
        project_name = self.project_name.text()
        folder_path = self.folder_path.text()
        product_name = self.product_name.text()
        version = self.version.currentText()
        if not version: 
            return
        representations = get_available_representations(project_name, folder_path, product_name, int(version))

        self.representation.clear()
        self.representation.addItems(representations)
        self.representation.setCurrentText(representations[0])    

    def updateNode(self, node):
        self.node = node