# ########################################################## ##
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
# ########################################################## ##

from PyQt5 import QtCore
import traceback


class Worker(QtCore.QObject):
    """
    Implements a queue of tasks to be carried out in order
    in a single independent thread.
    """

    # avoid multiple tests  for debug availability
    pydevd_failed = False
    task_completed = QtCore.pyqtSignal(str)

    def __init__(self, app, name=None):
        super(Worker, self).__init__()
        self.app = app
        self.name = name

    def allow_debug(self):
        """
         allow debuging/breakpoints in this threads
         should work from PyCharm and PyDev
        :return:
        """

        if not self.pydevd_failed:
            try:
                import pydevd
                pydevd.settrace(suspend=False, trace_only_current_thread=True)
            except ImportError:
                self.pydevd_failed = True

    def run(self):

        # self.app.log.debug("Worker Started!")

        self.allow_debug()

        # Tasks are queued in the event listener.
        self.app.worker_task.connect(self.do_worker_task)

    def do_worker_task(self, task):

        # self.app.log.debug("Running task: %s" % str(task))

        self.allow_debug()

        if ('worker_name' in task and task['worker_name'] == self.name) or \
                ('worker_name' not in task and self.name is None):

            try:
                task['fcn'](*task['params'])
            except Exception as e:
                self.app.thread_exception.emit(e)
                print(traceback.format_exc())
                # raise e
            finally:
                self.task_completed.emit(self.name)

        # self.app.log.debug("Task ignored.")
