# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
# ##########################################################

from appGUI.GUIElements import FlatCAMActivityView
from PyQt5 import QtCore
import weakref

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

# import logging

# log = logging.getLogger('base2')
# #log.setLevel(logging.DEBUG)
# log.setLevel(logging.WARNING)
# #log.setLevel(logging.INFO)
# formatter = logging.Formatter('[%(levelname)s] %(message)s')
# handler = logging.StreamHandler()
# handler.setFormatter(formatter)
# log.addHandler(handler)


class FCProcess(object):

    app = None

    def __init__(self, descr):
        self.callbacks = {
            "done": []
        }
        self.descr = descr
        self.status = "Active"

    def __del__(self):
        self.done()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.app.log.error("Abnormal termination of process!")
            self.app.log.error(exc_type)
            self.app.log.error(exc_val)
            self.app.log.error(exc_tb)

        self.done()

    def done(self):
        for fcn in self.callbacks["done"]:
            fcn(self)

    def connect(self, callback, event="done"):
        if callback not in self.callbacks[event]:
            self.callbacks[event].append(callback)

    def disconnect(self, callback, event="done"):
        try:
            self.callbacks[event].remove(callback)
        except ValueError:
            pass

    def set_status(self, status_string):
        self.status = status_string

    def status_msg(self):
        return self.descr


class FCProcessContainer(object):
    """
    This is the process container, or controller (as in MVC)
    of the Process/Activity tracking.

    FCProcessContainer keeps weak references to the FCProcess'es
    such that their __del__ method is called when the user
    looses track of their reference.
    """

    app = None

    def __init__(self):

        self.procs = []

    def add(self, proc):

        self.procs.append(weakref.ref(proc))

    def new(self, descr):
        proc = FCProcess(descr)

        proc.connect(self.on_done, event="done")

        self.add(proc)

        self.on_change(proc)

        return proc

    def on_change(self, proc):
        pass

    def on_done(self, proc):
        self.remove(proc)

    def remove(self, proc):

        to_be_removed = []

        for pref in self.procs:
            if pref() == proc or pref() is None:
                to_be_removed.append(pref)

        for pref in to_be_removed:
            self.procs.remove(pref)


class FCVisibleProcessContainer(QtCore.QObject, FCProcessContainer):
    something_changed = QtCore.pyqtSignal()
    # this will signal that the application is IDLE
    idle_flag = QtCore.pyqtSignal()

    def __init__(self, view):
        assert isinstance(view, FlatCAMActivityView), \
            "Expected a FlatCAMActivityView, got %s" % type(view)

        FCProcessContainer.__init__(self)
        QtCore.QObject.__init__(self)

        self.view = view

        self.text_to_display_in_activity = ''
        self.new_text = ' '

        self.something_changed.connect(self.update_view)

    def on_done(self, proc):
        # self.app.log.debug("FCVisibleProcessContainer.on_done()")
        super(FCVisibleProcessContainer, self).on_done(proc)

        self.something_changed.emit()

    def on_change(self, proc):
        # self.app.log.debug("FCVisibleProcessContainer.on_change()")
        super(FCVisibleProcessContainer, self).on_change(proc)

        # whenever there is a change update the message on activity
        self.text_to_display_in_activity = self.procs[0]().status_msg()

        self.something_changed.emit()

    def update_view(self):
        if len(self.procs) == 0:
            self.new_text = ''
            self.view.set_idle()
            self.idle_flag.emit()

        elif len(self.procs) == 1:
            self.view.set_busy(self.text_to_display_in_activity + self.new_text)
        else:
            self.view.set_busy("%d %s" % (len(self.procs), _("processes running.")))

    def update_view_text(self, new_text):
        # this has to be called after the method 'new' inherited by this class is called with a string text as param
        self.new_text = new_text
        if len(self.procs) == 1:
            self.view.set_busy(self.text_to_display_in_activity + self.new_text, no_movie=True)
