#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class MonoCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "mono"
        self.vocab = [
            (self.name, 'status', self.status),
            (self.name, 'init', self.initialise),
            (self.name, '@(shutter) @(open|close)', self.cmdShutter),
            (self.name, '@(set) <grating>', self.setGrating),
            (self.name, '@(set) <outport>', self.setOutport),
            (self.name, '@(set) <wave>', self.setWave),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__mono", (1, 1),
                                        keys.Key("grating", types.Int(), help="Grating Id"),
                                        keys.Key("outport", types.Int(), help="Outport Id"),
                                        keys.Key("wave", types.Float(), help="Wavelength"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))

    @threaded
    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        self.controller.getStatus(cmd)

    @threaded
    def initialise(self, cmd):
        """Initialise Bsh, call fsm startInit event """

        self.controller.substates.init(cmd=cmd)
        self.controller.getStatus(cmd)

    @threaded
    def cmdShutter(self, cmd):
        """Open/close , optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords

        openShutter = True if "open" in cmdKeys else "close"

        self.controller.setShutter(cmd=cmd, openShutter=openShutter)
        self.controller.getStatus(cmd)

    @threaded
    def setGrating(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        gratingId = int(cmdKeys["grating"].values[0])

        self.controller.setGrating(cmd=cmd, gratingId=gratingId)
        self.controller.getStatus(cmd)

    @threaded
    def setOutport(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        outportId = int(cmdKeys["outport"].values[0])

        self.controller.setOutport(cmd=cmd, outportId=outportId)
        self.controller.getStatus(cmd)

    @threaded
    def setWave(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        wavelength = float(cmdKeys["wave"].values[0])

        self.controller.setWave(cmd=cmd, wavelength=wavelength)
        self.controller.getStatus(cmd)
