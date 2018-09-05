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
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__mono", (1, 1),
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

