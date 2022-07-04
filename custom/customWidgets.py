""" customWidgets defines widgets with customized functionalities """

from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STYLESHEET = """ QLineEdit {font: 14px} """


class Tableview(QtWidgets.QTableView):
    """ custom QTableView widget """

    dropped = pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # set properties
        self.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)

        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QTableView.DragDrop)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """ on drop filter on the files """
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            # event handled
            event.accept()
            # emit only files
            self.dropped.emit(files)
        else:
            super().dropEvent(event)


class PathEdit(QtWidgets.QLineEdit):
    """ custom QLineEdit with a trailing action """

    def __init__(self, chooser_title, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.caption = chooser_title
        self.last_known_dir = os.path.expanduser(f"~{os.sep}Documents")

        add_action = QtWidgets.QAction(parent=self)
        # since cwd is based on controller.py, path starts at custom/data/png
        add_action.setIcon(QIcon(f"custom{os.sep}data{os.sep}add_folder.png"))
        add_action.setToolTip("Browse")
        add_action.triggered.connect(self.get_dir)

        self.addAction(add_action, QtWidgets.QLineEdit.TrailingPosition)
        self.setToolTip("Type path to browser")

    def get_dir(self):
        """ set abs folder str """
        folder = os.path.normpath(QtWidgets.QFileDialog.getExistingDirectory(
            self, caption=f"{self.caption}",
            directory=self.last_known_dir,
        ))
        if folder and (folder != "."):
            self.last_known_dir = folder
            self.setText(folder)
