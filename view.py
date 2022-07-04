""" view presents data to the user """

from typing import Iterable
from custom import customWidgets
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout, QVBoxLayout,
    QListWidget, QLabel, QPushButton,
    QProgressBar,
)

from utils import Transfer, convert_bytes, _basename
from PyQt5.QtCore import QModelIndex, Qt, pyqtSignal, QThreadPool, QTimer


STYLESHEET = """QWidget {
    font: 13px;
}"""


class DuplicatesWindow(QWidget):
    """
    window for displaying duplicate files
    inherits:
        QWidget
    """

    def __init__(self, files: Iterable[str], *args):

        super().__init__(*args)
        self.setWindowTitle("Feedback")
        self.setFixedSize(600, 300)

        vlayout = QVBoxLayout()

        details_label = QLabel("These files already exist in the destination folder:")
        list_widget = QListWidget()
        list_widget.addItems(files)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.deleteLater)

        vlayout.addWidget(details_label)
        vlayout.addWidget(list_widget)
        vlayout.addWidget(ok_btn, alignment=Qt.AlignRight)
        self.setLayout(vlayout)


class TransferWindow(QWidget):
    """
    window for displaying transfer progress
    inherits:
        QWidget
    """

    def __init__(self, *args):

        super().__init__(*args)
        self.setWindowTitle("Transfering")
        self.setFixedSize(400, 150)

        main_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        self.cancel_transfer = QPushButton("Cancel")
        btn_layout.addWidget(self.cancel_transfer, alignment=Qt.AlignRight)
        self.transfer_to = QLabel("Transfering to:")
        self.percentage_progress = QLabel("0%")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(0)
        self.remaining_files = QLabel("0 Files Remaining", self)

        main_layout.addWidget(self.transfer_to)
        main_layout.addWidget(self.percentage_progress)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.remaining_files)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)


class WorkerManager(TransferWindow):
    """
    Manager to handle our worker queues and state
    inherits:
        TransferWindow: transfer GUI
    assumes:
        all workers/runnables are the same
    """

    _workers_progress = {}
    _active_workers = {}
    _transferred = {}
    all_done = pyqtSignal()

    def __init__(self):
        super().__init__()
        # create a threadpool for workers
        self.files_threadpool = QThreadPool()
        self.files_threadpool.setMaxThreadCount(1)
        self.timer = QTimer()
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh_progress)
        self.timer.start()
        self.total_workers = 0
        self.total_size = 0
        self.duplicates = []
        self.cancel_transfer.clicked.connect(self.cancel)

    def enqueue(self, worker: Transfer):
        """ Enqueue a worker to run (at some point) by passing it to the QThreadPool """

        if self.is_valid(worker):

            worker.signals.progress.connect(self.receive_progress)
            worker.signals.finished.connect(self.done)
            worker.signals.transferred.connect(self.receive_transferred)
            worker.signals.duplicate.connect(self.receive_dups)
            self._active_workers[worker.job_id] = worker
            self.total_workers += 1
            self.total_size += worker.size
            self.files_threadpool.start(worker)

            print(f"Total size {self.total_size} Bytes")
            self.show()

    def receive_progress(self, job_id, progress):
        self._workers_progress[job_id] = progress

    def receive_transferred(self, job_id, size):
        self._transferred[job_id] = size

    def receive_dups(self, file):
        self.duplicates.append(file)

    def calculate_progress(self):
        """ Calculate total progress """
        if not self._workers_progress or not self.total_workers:
            return 0
        return sum(v for v in self._workers_progress.values()) / self.total_workers

    def calculate_transferred(self):
        if not self._transferred:
            return 0
        return sum(v for v in self._transferred.values())

    def refresh_progress(self):
        """ get and update progress """
        progress = int(self.calculate_progress())
        transferred = self.calculate_transferred()
        rem_size = convert_bytes(self.total_size - transferred)
        rem_files = max(1, len(self._active_workers))

        self.progress_bar.setValue(progress)
        self.percentage_progress.setText(f"{progress}%")
        self.remaining_files.setText(f"{rem_files} remaining ({rem_size})")

    def done(self, job_id):
        """ Remove workers when all jobs are done 100% """
        # avoid KeyError
        if self._active_workers:
            del self._active_workers[job_id]
        if all(v == 100 for v in self._workers_progress.values()) and not (self._active_workers):
            self._workers_progress.clear()
            self._transferred.clear()
            self.total_workers = 0
            self.total_size = 0
            self.all_done.emit()
            self.handle_dups()
            self.hide()

    def cancel(self):
        """ cancel transfer """
        self.files_threadpool.clear()
        for w in self._active_workers.values():
            w.running = 0
        self._active_workers.clear()
        # self.hide()

    def handle_dups(self):
        if self.duplicates:
            self.w = DuplicatesWindow(self.duplicates)
            self.w.setWindowIcon(self.windowIcon())
            self.duplicates.clear()
            self.w.show()

    def is_valid(self, worker):
        """ if file is valid for transfer """
        remaining = {worker.src: (worker.src, worker.dst) for worker in self._active_workers.values()}
        worker_src = worker.src
        if worker_src in remaining:
            src, dst = remaining[worker_src]
            if (src == worker_src) and (dst == worker.dst):
                print("The same file is scheduled for the same destination folder")
                return False
        return True


class MainWindow(QMainWindow):
    """ main window code """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)

        self.setWindowTitle("DragnDrop")
        self.setMinimumSize(1100, 400)

        main_layout = QVBoxLayout()
        inputs_layout = QHBoxLayout()
        tables_layout = QHBoxLayout()
        main_layout.addLayout(inputs_layout)
        main_layout.addLayout(tables_layout)

        self.table_holder = QWidget()
        self.table_holder.setLayout(main_layout)

        self.right_input = customWidgets.PathEdit("Choose folder to open right")
        self.left_input = customWidgets.PathEdit("Choose folder to open left")

        # create tables
        self.right_table = customWidgets.Tableview()
        self.left_table = customWidgets.Tableview()
        # add inputs
        inputs_layout.addWidget(self.left_input)
        inputs_layout.addWidget(self.right_input)
        # add tables
        tables_layout.addWidget(self.left_table)
        tables_layout.addWidget(self.right_table)

        self.setCentralWidget(self.table_holder)
        self.setStyleSheet(STYLESHEET)

        # show window; optionally, this can be called in the controller after model setup
        # self.showMaximized()

        self.transfersManager = WorkerManager()

    def setupModelRight(self, model):
        """ set up model for the right table and update GUI accordingly """
        self.right_table.setModel(model)

    def setupModelLeft(self, model):
        """ set up model for the left table """
        self.left_table.setModel(model)

    def rootIndexRight(self, root_index=QModelIndex()):
        """ set the right root display path index """
        self.right_table.setRootIndex(root_index)

    def rootIndexLeft(self, root_index=QModelIndex()):
        """ set the left root display path index """
        self.left_table.setRootIndex(root_index)

    def changePathRight(self, path):
        """ change text of right input """
        self.right_input.setText(path)

    def changePathLeft(self, path):
        """ change text of left input """
        self.left_input.setText(path)

    def updateStatus(self, txt):
        """ """
        self.status_bar.setStatusTip(txt)

    def enqueueTransfer(self, worker: Transfer):
        """ enqueue transfer worker/runnables """
        self.transfersManager.enqueue(worker)

    def changeTransferTitle(self, task, dst):
        """
        change transfer window title
        like; Moving to 'C:\\Users'
        """
        self.transfersManager.transfer_to.setText(f"{task} to '{_basename(dst)}'...")
