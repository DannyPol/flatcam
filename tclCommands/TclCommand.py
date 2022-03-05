import sys
import re
import app_Main
import abc
import collections
from PyQt5 import QtCore
from contextlib import contextmanager


class TclCommand(object):

    # FlatCAMApp
    app = None

    # Logger
    log = None

    # List of all command aliases, to be able use  old names
    # for backward compatibility (add_poly, add_polygon)
    aliases = []

    # Dictionary of types from Tcl command, needs to be ordered
    # OrderedDict should be like collections.OrderedDict([(key,value),(key2,value2)])
    arg_names = collections.OrderedDict([
        ('name', str)
    ])

    # dictionary of types from Tcl command, needs to be ordered.
    # This  is  for options  like -optionname value.
    # OrderedDict should be like collections.OrderedDict([(key,value),(key2,value2)])
    option_types = collections.OrderedDict()

    # List of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['name']

    # Structured help for current command, args needs to be ordered
    # OrderedDict should be like collections.OrderedDict([(key,value),(key2,value2)])
    help = {
        'main': "undefined help.",
        'args': collections.OrderedDict([
            ('argumentname', 'undefined help.'),
            ('optionname', 'undefined help.')
        ]),
        'examples': []
    }

    # Original incoming arguments into command
    original_args = None

    def __init__(self, app):
        self.app = app

        if self.app is None:
            raise TypeError('Expected app to be FlatCAMApp instance.')

        if not isinstance(self.app, app_Main.App):
            raise TypeError('Expected FlatCAMApp, got %s.' % type(app))

        self.log = self.app.log
        self.error_info = None
        self.error = None

    def raise_tcl_error(self, text):
        """
        This method pass exception from python into TCL as error
        so we get stacktrace and reason.

        This is only redirect to self.app.raise_tcl_error

        :param text: text of error
        :return: none
        """

        self.app.shell.raise_tcl_error(text)

    def get_current_command(self):
        """
        Get current command, we are not able to get it from TCL we have to reconstruct it.

        :return: current command
        """
        command_string = [self.aliases[0]]

        if self.original_args is not None:
            for arg in self.original_args:
                command_string.append(arg)

        return " ".join(command_string)

    def get_decorated_help(self):
        """
        Decorate help for TCL console output.

        :return: decorated help from structure
        """

        def get_decorated_command(alias_name):

            command_string = []

            for arg_key, arg_type in list(self.help['args'].items()):
                command_string.append(get_decorated_argument(arg_key, arg_type, True))

            return "> " + alias_name + " " + " ".join(command_string)

        def get_decorated_argument(help_key, help_text, in_command=False):
            """

            :param help_key: Name of the argument.
            :param help_text:
            :param in_command:
            :return:
            """
            option_symbol = ''

            if help_key in self.arg_names:
                arg_type = self.arg_names[help_key]
                type_name = str(arg_type.__name__)
                # in_command_name = help_key + "<" + type_name + ">"
                in_command_name = help_key

            elif help_key in self.option_types:
                option_symbol = '-'
                arg_type = self.option_types[help_key]
                type_name = str(arg_type.__name__)
                in_command_name = option_symbol + help_key + " <" + type_name + ">"

            else:
                option_symbol = ''
                type_name = '?'
                in_command_name = option_symbol + help_key + " <" + type_name + ">"

            if in_command:
                if help_key in self.required:
                    return in_command_name
                else:
                    return '[' + in_command_name + "]"
            else:
                if help_key in self.required:
                    return "\t" + option_symbol + help_key + " <" + type_name + ">: " + help_text
                else:
                    return "\t[" + option_symbol + help_key + " <" + type_name + ">: " + help_text + "]"

        def get_decorated_example(example_item):
            return "> " + example_item

        help_string = [self.help['main']]
        for alias in self.aliases:
            help_string.append(get_decorated_command(alias))

        for key, value in list(self.help['args'].items()):
            help_string.append(get_decorated_argument(key, value))

        # timeout is unique for signaled commands (this is not best oop practice, but much easier for now)
        if isinstance(self, TclCommandSignaled):
            help_string.append("\t[-timeout <int>: Max wait for job timeout before error.]")

        for example in self.help['examples']:
            help_string.append(get_decorated_example(example))

        return "\n".join(help_string)

    @staticmethod
    def parse_arguments(args):
        """
        Pre-processes arguments to detect '-keyword value' pairs into dictionary
        and standalone parameters into list.

        This is copy from FlatCAMApp.setup_shell().h() just for accessibility,
        original should  be removed  after all commands will be converted

        :param args: arguments from tcl to parse
        :return: arguments, options
        """

        options = {}
        arguments = []
        n = len(args)

        option_name = None

        for i in range(n):
            match = re.search(r'^-([a-zA-Z].*)', args[i])
            if match:
                # assert option_name is None
                if option_name is not None:
                    options[option_name] = None

                option_name = match.group(1)
                continue

            if option_name is None:
                arguments.append(args[i])
            else:
                options[option_name] = args[i]
                option_name = None

        if option_name is not None:
            options[option_name] = None

        return arguments, options

    def check_args(self, args):
        """
        Check arguments and options for right types

        :param args: arguments from tcl to check
        :return: named_args, unnamed_args
        """

        arguments, options = self.parse_arguments(args)
        named_args = {}
        unnamed_args = []

        # check arguments
        idx = 0
        arg_names_items = list(self.arg_names.items())
        for argument in arguments:
            if len(self.arg_names) > idx:
                key, arg_type = arg_names_items[idx]

                try:
                    named_args[key] = arg_type(argument)
                except Exception as e:
                    self.raise_tcl_error("Cannot cast named argument '%s' to type %s  with exception '%s'."
                                         % (key, arg_type, str(e)))
            else:
                unnamed_args.append(argument)
            idx += 1

        # check options
        for key in options:
            if key not in self.option_types and key != 'timeout':
                self.raise_tcl_error('Unknown parameter: %s' % key)
            try:
                if key != 'timeout':
                    # None options are allowed; if None then the defaults are used
                    # - must be implemented in the Tcl commands
                    if options[key] is not None:
                        named_args[key] = self.option_types[key](options[key])
                    else:
                        named_args[key] = options[key]
                else:
                    named_args[key] = int(options[key])
            except Exception as e:
                self.raise_tcl_error("Cannot cast argument '-%s' to type '%s' with exception '%s'."
                                     % (key, self.option_types[key], str(e)))

        # check required arguments
        for key in self.required:
            if key not in named_args:
                self.raise_tcl_error("Missing required argument '%s'." % key)

        return named_args, unnamed_args

    def raise_tcl_unknown_error(self, unknown_exception):
        """
        raise Exception if is different type  than TclErrorException
        this is here mainly to show unknown errors inside TCL shell console

        :param unknown_exception:
        :return:
        """

        raise unknown_exception

    def raise_tcl_error(self, text):
        """
        this method  pass exception from python into TCL as error, so we get stacktrace and reason
        :param text: text of error
        :return: raise exception
        """

        # because of signaling we cannot call error to TCL from here but when task
        # is finished also non-signaled are handled here to better exception
        # handling and  displayed after command is finished
        raise self.app.shell.TclErrorException(text)

    def execute_wrapper(self, *args):
        """
        Command which is called by tcl console when current commands aliases are hit.
        Main catch(except) is implemented here.
        This method should be reimplemented only when initial checking sequence differs

        :param args: arguments passed from tcl command console
        :return: None, output text or exception
        """

        # self.worker_task.emit({'fcn': self.exec_command_test, 'params': [text, False]})
        try:
            self.log.debug("TCL command '%s' executed." % str(type(self).__name__))
            self.original_args = args
            args, unnamed_args = self.check_args(args)
            return self.execute(args, unnamed_args)
        except Exception as unknown:
            error_info = sys.exc_info()
            self.log.error("TCL command '%s' failed. Error text: %s" % (str(self), str(unknown)))
            self.app.shell.display_tcl_error(unknown, error_info)
            self.raise_tcl_unknown_error(unknown)

    @abc.abstractmethod
    def execute(self, args, unnamed_args):
        """
        Direct execute of command, this method should be implemented in each descendant.
        No main catch should be implemented here.

        :param args: array of known named arguments and options
        :param unnamed_args: array of other values which were passed into command
            without -somename and  we do not have them in known arg_names
        :return: None, output text or exception
        """

        raise NotImplementedError("Please Implement this method")


class TclCommandSignaled(TclCommand):
    """
        !!! I left it here only  for demonstration !!!
        Go to TclCommandCncjob and  into class definition put
            class TclCommandCncjob(TclCommandSignaled):
        also change
            obj.generatecncjob(use_thread = False, **args)
        to
            obj.generatecncjob(use_thread = True, **args)


        This class is  child of  TclCommand and is used for commands  which create  new objects
        it handles  all necessary stuff about blocking and passing exceptions
    """

    @abc.abstractmethod
    def execute(self, args, unnamed_args):
        raise NotImplementedError("Please Implement this method")

    output = None

    def execute_call(self, args, unnamed_args):

        try:
            self.output = None
            self.error = None
            self.error_info = None
            self.output = self.execute(args, unnamed_args)
        except Exception as unknown:
            self.error_info = sys.exc_info()
            self.error = unknown
        finally:
            self.app.shell_command_finished.emit(self)

    def execute_wrapper(self, *args):
        """
        Command which is called by tcl console when current commands aliases are hit.
        Main catch(except) is implemented here.
        This method should be reimplemented only when initial checking sequence differs

        :param args: arguments passed from tcl command console
        :return: None, output text or exception
        """

        @contextmanager
        def wait_signal(signal, timeout=300000):
            """Block loop until signal emitted, or timeout (ms) elapses."""
            loop = QtCore.QEventLoop()

            # Normal termination
            signal.connect(loop.quit)

            # Termination by exception in thread
            self.app.thread_exception.connect(loop.quit)

            status = {'timed_out': False}

            def report_quit():
                status['timed_out'] = True
                loop.quit()

            yield

            # Temporarily change how exceptions are managed.
            oeh = sys.excepthook
            ex = []

            def except_hook(type_, value, traceback_):
                ex.append(value)
                oeh(type_, value, traceback_)
            sys.excepthook = except_hook

            # Terminate on timeout
            if timeout is not None:
                time_val = int(timeout)
                QtCore.QTimer.singleShot(time_val, report_quit)

            # Block
            loop.exec_()

            # Restore exception management
            sys.excepthook = oeh
            if ex:
                raise ex[0]

            if status['timed_out']:
                self.app.shell.raise_tcl_unknown_error("Operation timed outed! Consider increasing option "
                                                       "'-timeout <miliseconds>' for command or "
                                                       "'set_sys global_background_timeout <miliseconds>'.")

        try:
            self.log.debug("TCL command '%s' executed." % str(type(self).__name__))
            self.original_args = args
            args, unnamed_args = self.check_args(args)
            if 'timeout' in args:
                passed_timeout = args['timeout']
                del args['timeout']
            else:
                passed_timeout = self.app.defaults['global_background_timeout']

            # set detail for processing, it will be there until next open or close
            self.app.shell.open_processing(self.get_current_command())

            def handle_finished():
                self.app.shell_command_finished.disconnect(handle_finished)
                if self.error is not None:
                    self.raise_tcl_unknown_error(self.error)

            self.app.shell_command_finished.connect(handle_finished)

            with wait_signal(self.app.shell_command_finished, passed_timeout):
                # every TclCommandNewObject ancestor  support  timeout as parameter,
                # but it does not mean anything for child itself
                # when operation  will be  really long is good  to set it higher then defqault 30s
                self.app.worker_task.emit({'fcn': self.execute_call, 'params': [args, unnamed_args]})

            return self.output

        except Exception as unknown:
            # if error happens inside thread execution, then pass correct error_info to display
            if self.error_info is not None:
                error_info = self.error_info
            else:
                error_info = sys.exc_info()
            self.log.error("TCL command '%s' failed." % str(self))
            self.app.shell.display_tcl_error(unknown, error_info)
            self.raise_tcl_unknown_error(unknown)
