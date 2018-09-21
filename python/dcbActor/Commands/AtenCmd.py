#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class AtenCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "aten"
        self.vocab = [
            (self.name, 'status', self.status),
            ('power', '@(on|off) @(<channel>|<channels>|labsphere)', self.switch),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__aten", (1, 1),
                                        keys.Key("channel", types.String(), help="which channel to power on"),
                                        keys.Key("channels", types.String() * (1,), help="which channels to power on"),
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
    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords

        if 'labsphere' in cmdKeys:
            channels = ["pow_attenuator", "pow_sphere", "pow_halogen"]

        elif "channels" in cmdKeys:
            channels = cmdKeys["channels"].values
        else:
            channels = [cmdKeys["channel"].values[0]]

        bool = 'on' if "on" in cmdKeys else 'off'

        self.controller.substates.switch(cmd=cmd, channels=channels, bool=bool)
