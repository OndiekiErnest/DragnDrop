""" controller links the data model and the view """

from model import QFileSystemModel
from view import MainWindow
from PyQt5.QtWidgets import QApplication
from os.path import (
    exists, splitdrive,
    abspath, dirname, join,
    isdir, isfile, getsize,
    normpath,
)

from os import startfile, scandir, mkdir
import utils
import sys

BASE_DIR = dirname(abspath(__file__))
HOME_DIR = splitdrive(BASE_DIR)[0]


class Main():
    """ controller main class for dualpane """

    def __init__(self):
        self.rightValidPath = HOME_DIR
        self.leftValidPath = HOME_DIR

        self.rightModel = QFileSystemModel()
        self.rightModel.setReadOnly(True)
        self.leftModel = QFileSystemModel()
        self.rightModel.setReadOnly(True)

        self.rightParentIndex = self.rightModel.setRootPath("")
        self.leftParentIndex = self.leftModel.setRootPath("")

        self.mainWindow = MainWindow()

        self.mainWindow.setupModelRight(self.rightModel)
        self.mainWindow.setupModelLeft(self.leftModel)

        # on type
        self.mainWindow.right_input.textChanged.connect(self.update_right)
        self.mainWindow.left_input.textChanged.connect(self.update_left)

        # on double-click
        self.mainWindow.right_table.doubleClicked.connect(self.rightDoubleClicked)
        self.mainWindow.left_table.doubleClicked.connect(self.leftDoubleClicked)

        # on files dropped
        self.mainWindow.right_table.dropped.connect(self.startTransferRight)
        self.mainWindow.left_table.dropped.connect(self.startTransferLeft)

        # show window
        self.mainWindow.showMaximized()

    def update_right(self, path):
        """ on path changes """
        if (exists(path) and isdir(path)) or (not path):
            self.rightValidPath = path or HOME_DIR
            self.rightParentIndex = self.rightModel.setRootPath(path)
            self.mainWindow.rootIndexRight(root_index=self.rightModel.index(path))

    def update_left(self, path):
        """ on path changes """
        if (exists(path) and isdir(path)) or (not path):
            self.leftValidPath = path or HOME_DIR
            self.leftParentIndex = self.leftModel.setRootPath(path)
            self.mainWindow.rootIndexLeft(root_index=self.leftModel.index(path))

    def rightDoubleClicked(self, index):
        """ index is a QModelIndex """
        pathIndex = self.rightModel.index(index.row(), 0, self.rightParentIndex)
        path = normpath(self.rightModel.filePath(pathIndex))

        if isdir(path):
            self.mainWindow.changePathRight(path)
        elif isfile(path):
            startfile(path)

    def leftDoubleClicked(self, index):
        """ index is a QModelIndex """
        pathIndex = self.leftModel.index(index.row(), 0, self.leftParentIndex)
        path = normpath(self.leftModel.filePath(pathIndex))

        if isdir(path):
            self.mainWindow.changePathLeft(path)
        elif isfile(path):
            startfile(path)

    def createWorker(self, src, dst):
        """ create transfer instance and enqueue it """
        file_size = getsize(src)
        worker = utils.Transfer(src, dst, file_size)
        self.mainWindow.enqueueTransfer(worker)

    def startTransferRight(self, files: list):
        """ initiate file transfers """
        self.mainWindow.changeTransferTitle("Copying", self.rightValidPath)
        for src in files:
            if isfile(src):
                self.createWorker(src, self.rightValidPath)
            elif isdir(src):
                self.transferFolder(src, self.rightValidPath)

    def startTransferLeft(self, files: list):
        """ initiate file transfers """
        self.mainWindow.changeTransferTitle("Copying", self.leftValidPath)
        for src in files:
            if isfile(src):
                self.createWorker(src, self.leftValidPath)
            elif isdir(src):
                self.transferFolder(src, self.leftValidPath)

    def transferFolder(self, src: str, dst: str):
        """ loop files recursively in src folder """
        dst_name = utils._basename(src) or f"Removable Disk ({src[0]})"
        dst = join(dst, dst_name)

        if not exists(dst):
            mkdir(dst)
        for entry in scandir(src):
            if entry.is_file():
                self.createWorker(entry.path, dst)
            elif entry.is_dir():
                self.transferFolder(entry.path, dst)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    controller = Main()

    sys.exit(app.exec())
