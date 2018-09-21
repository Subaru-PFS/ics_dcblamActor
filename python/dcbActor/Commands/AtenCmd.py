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
            ('power', '[<on>] [<off>]', self.switch),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__aten", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
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

        switchOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        switchOff = cmdKeys['off'].values if 'off' in cmdKeys else []

        self.controller.substates.switch(cmd=cmd, switchOn=switchOn, switchOff=switchOff)
        cmd.finish()
