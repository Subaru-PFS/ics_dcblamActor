#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class LabsphereCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "labsphere"
        self.vocab = [
            (self.name, 'status', self.status),
            (self.name, '<attenuator>', self.moveAttenuator),
            (self.name, '@(halogen) @(on|off)', self.switchHalogen),
            (self.name, 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb_labsphere", (1, 1),
                                        keys.Key("channel", types.String(), help="which channel to power on"),
                                        keys.Key("attenuator", types.Int(), help="attenuator value"),
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

        self.controller.generate(cmd)

    @threaded
    def moveAttenuator(self, cmd):
        cmdKeys = cmd.cmd.keywords

        value = cmdKeys['attenuator'].values[0]
        if value != self.controller.attenuator:
            self.controller.substates.move(cmd=cmd, value=value)
        self.controller.generate(cmd)

    @threaded
    def initialise(self, cmd):

        self.controller.substates.init(cmd=cmd)
        self.controller.generate(cmd)

    @threaded
    def switchHalogen(self, cmd):
        cmdKeys = cmd.cmd.keywords

        state = 'on' if 'on' in cmdKeys else 'off'

        self.controller.substates.halogen(cmd=cmd, state=state)
        self.controller.generate(cmd)
