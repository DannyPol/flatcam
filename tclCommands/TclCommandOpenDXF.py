from tclCommands.TclCommand import TclCommandSignaled

import collections


class TclCommandOpenDXF(TclCommandSignaled):
    """
    Tcl shell command to open an DXF file as a Geometry/Gerber Object.
    """

    # array of all command aliases, to be able use  old names for backward compatibility (add_poly, add_polygon)
    aliases = ['open_dxf']

    description = '%s %s' % ("--", "Open a DXF file as a Geometry (or Gerber) Object.")

    # dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([
        ('filename', str)
    ])

    # dictionary of types from Tcl command, needs to be ordered , this  is  for options  like -optionname value
    option_types = collections.OrderedDict([
        ('type', str),
        ('outname', str)
    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['filename']

    # structured help for current command, args needs to be ordered
    help = {
        'main': "Open a DXF file as a Geometry (or Gerber) Object.",
        'args':  collections.OrderedDict([
            ('filename', 'Absolute path to file to open. Required.\n'
                         'WARNING: no spaces are allowed. If unsure enclose the entire path with quotes.'),
            ('type', 'Open as a Gerber or Geometry (default) object. Values can be: "geometry" or "gerber"'),
            ('outname', 'Name of the resulting Geometry object.')
        ]),
        'examples': ['open_dxf D:\\my_beautiful_svg_file.SVG']
    }

    def execute(self, args, unnamed_args):
        """
        execute current TCL shell command

        :param args: array of known named arguments and options
        :param unnamed_args: array of other values which were passed into command
            without -somename and  we do not have them in known arg_names
        :return: None or exception
        """

        # How the object should be initialized
        def obj_init(geo_obj, app_obj):

            # if geo_obj.kind != 'geometry' and geo_obj.kind != 'gerber':
            #     self.raise_tcl_error('Expected Geometry or Gerber, got %s %s.' % (outname, type(geo_obj)))
            if obj_type == "geometry":
                geo_obj.import_dxf_as_geo(filename, units=units)
            elif obj_type == "gerber":
                geo_obj.import_dxf_as_gerber(filename, units=units)
            else:
                return "fail"

        filename = args['filename']

        if 'outname' in args:
            outname = args['outname']
        else:
            outname = filename.split('/')[-1].split('\\')[-1]

        if 'type' in args:
            obj_type = str(args['type']).lower()
        else:
            obj_type = 'geometry'

        if obj_type != "geometry" and obj_type != "gerber":
            self.raise_tcl_error("Option type can be 'geometry' or 'gerber' only, got '%s'." % obj_type)

        units = self.app.defaults['units'].upper()

        with self.app.proc_container.new('%s' % _("Opening ...")):

            # Object creation
            ret_val = self.app.app_obj.new_object(obj_type, outname, obj_init, plot=False)
            if ret_val == 'fail':
                filename = self.app.defaults['global_tcl_path'] + '/' + outname
                ret_val = self.app.app_obj.new_object(obj_type, outname, obj_init, plot=False)
                self.app.shell.append_output(
                    "No path provided or path is wrong. Using the default Path... \n")

                if ret_val == 'fail':
                    return "Failed. The OpenDXF command was used but could not open the DXF file"

            # Register recent file
            self.app.file_opened.emit("dxf", filename)

            # GUI feedback
            self.app.inform.emit("Opened: " + filename)
