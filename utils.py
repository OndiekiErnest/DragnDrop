from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot, QRunnable
from send2trash import send2trash, TrashPermissionError
import shutil
import uuid
import os


ON_SUCCESS = 1
ON_CANCEL = 2
ON_ERROR = 3


class TransferSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    finished
    `str` transfer id
    progress
    `int` indicating % progress
    """
    __slots__ = ()

    finished = pyqtSignal(str)
    progress = pyqtSignal(str, int)
    transferred = pyqtSignal(str, float)
    duplicate = pyqtSignal(str)


class Transfer(QRunnable):
    """
    File transfer runnable
    Runs on a different thread
    inherits:
        QRunnable
    parameters:
        `src`: str file path
        `dst`: str file/dir path
        `size`: float `src` file size in bytes
    """
    __slots__ = (
        "src", "dst", "size",
        "signals", "running", "job_id")

    def __init__(self, src, dst, size):
        super().__init__()
        self.src = src
        self.dst = dst
        # create dst file
        if os.path.isdir(dst):
            self.dst = os.path.join(dst, _basename(src))
        self.size = size
        self.signals = TransferSignals()
        self.running = 0
        # Give this job a unique ID.
        self.job_id = str(uuid.uuid4())

    @pyqtSlot()
    def run(self):
        # run the specified function
        if file_exists(self.src, self.dst):
            # end prematurely and emit dst
            print(f"File already exists '{self.dst}'")
            self.signals.duplicate.emit(self.dst)
            self.signals.progress.emit(self.job_id, 100)
            self.signals.finished.emit(self.job_id)

        else:
            self.copy(self.src, self.dst)

    def _copyfileobj_readinto(self, fsrc, fdst, length=1048576):
        """
        readinto()/memoryview()-based variant of copyfileobj()
        *fsrc* must support readinto() method and both files must be
        open in binary mode.
        """
        print(f"Transferring, method: readinto, buffer: {length}")
        progress = 0
        self.running = 1
        # localize variable access to minimize overhead
        fsrc_readinto = fsrc.readinto
        fdst_write = fdst.write
        with memoryview(bytearray(length)) as mv:
            try:
                while 1:
                    n = fsrc_readinto(mv)
                    if not n:
                        self.signals.finished.emit(self.job_id)
                        self.running = 0
                        print("Successful transfer")
                        return ON_SUCCESS

                    elif n < length:
                        with mv[:n] as smv:
                            fdst.write(smv)
                    else:
                        fdst_write(mv)
                    progress += n
                    percentage = (progress * 100) / self.size
                    self.signals.transferred.emit(self.job_id, progress)
                    self.signals.progress.emit(self.job_id, percentage)
                    # handle cancel
                    if not self.running:
                        print("Cancelled transfer")
                        self.signals.progress.emit(self.job_id, 100)
                        self.signals.finished.emit(self.job_id)
                        return ON_CANCEL
            except Exception as e:
                print(f"Error in transferring: {str(e)}")
                self.running = 0
                self.signals.progress.emit(self.job_id, 100)
                self.signals.finished.emit(self.job_id)
                return ON_ERROR

    def _copyfileobj(self, fsrc, fdst, length=1048576):
        """
        copy data from file-like object fsrc to file-like object fdst
        return success
        """
        print(f"Transferring, method: copy-buffer, buffer: {length}")
        progress = 0
        self.running = 1
        # localize variables to avoid overhead
        fsrc_read = fsrc.read
        fdst_write = fdst.write
        try:
            while 1:
                buff = fsrc_read(length)
                if not buff:
                    self.signals.finished.emit(self.job_id)
                    self.running = 0
                    # break and return success
                    print("Successful transfer")
                    return ON_SUCCESS

                fdst_write(buff)
                progress += len(buff)
                percentage = (progress * 100) / self.size
                self.signals.transferred.emit(self.job_id, progress)
                self.signals.progress.emit(self.job_id, percentage)
                # handle cancel
                if not self.running:
                    print("Cancelled transfer")
                    self.signals.progress.emit(self.job_id, 100)
                    self.signals.finished.emit(self.job_id)
                    return ON_CANCEL

        except Exception as e:
            print(f"Error in transferring: {str(e)}")
            self.running = 0
            self.signals.progress.emit(self.job_id, 100)
            self.signals.finished.emit(self.job_id)
            return ON_ERROR

    def _copyfile(self, src, dst):
        """ check if file exists, if same filesystem, else prepare file objects """

        try:
            # prepare file objects for read/write
            with open(src, 'rb') as fsrc:
                with open(dst, 'wb') as fdst:
                    if self.size > 0:
                        return self._copyfileobj_readinto(fsrc, fdst, length=min(1048576, self.size))
                    # copy files with 0 sizes
                    return self._copyfileobj(fsrc, fdst)
        except PermissionError:
            self.signals.progress.emit(self.job_id, 100)
            self.signals.finished.emit(self.job_id)
            return ON_ERROR

    def copy(self, src, dst):
        """ rename folders and prepare files for copying """

        done = self._copyfile(src, dst)
        if done == ON_SUCCESS:
            # copy file, then copy file stats
            self.copy_stat(src, dst)
        if done == ON_CANCEL:
            # clean up incomplete dst file

            print(f"Deleting incomplete file '{dst}'")
            delete_file(dst)
        return done

    def copy_stat(self, src, dst):
        try:
            shutil.copystat(src, dst)
        except Exception as e:
            print(f"Stats error: {e}")


def _basename(path):
    """ strip trailing slash and return basename """
    # A basename() variant which first strips the trailing slash, if present.
    # Thus we always get the last component of the path, even for directories.
    # borrowed from shutil.py
    sep = os.path.sep + (os.path.altsep or '')
    return os.path.basename(path.rstrip(sep))


def file_exists(src, dst) -> bool:
    """ compare file properties """
    if os.path.isdir(dst):
        dst = os.path.join(dst, _basename(src))
    if os.path.exists(dst):
        # return (os.path.getsize(src) == os.path.getsize(dst))
        return True
    return False


def delete_file(filename, trash=False):
    """
    permanently delete a file if `trash` is False
    """
    if trash:
        try:
            send2trash(filename)
        except TrashPermissionError as e:
            print(f"Cannot trash file: {e}")
    else:
        try:
            os.unlink(filename)
        except Exception as e:
            print(f"Cannot remove file: {e}")


def convert_bytes(num: float) -> str:
    """ format bytes to respective units for presentation (max GB) """
    try:
        if num >= 1073741824:
            return f"{round(num / 1073741824, 2)} GB"
        elif num >= 1048576:
            return f"{round(num / 1048576, 2)} MB"
        elif num >= 1024:
            return f"{round(num / 1024, 2)} KB"
        else:
            return f"{num} Bytes"
    except Exception:
        return "NaN"
