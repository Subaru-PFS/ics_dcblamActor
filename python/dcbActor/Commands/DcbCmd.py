#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types


class DcbCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('switch', '@(on|off) [<channel>]', self.switch),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb_dcb", (1, 1),
                                        keys.Key("channel", types.String(), help="which channel to power on"),

                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords
        channel = cmdKeys["channel"].values[0]
        
        ret = self.actor.compute(expTime)
        cmd.finish("result=%.2f" % ret)
