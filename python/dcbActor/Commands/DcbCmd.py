#!/usr/bin/env python

import sys

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

    def status(self, cmd, channel=None):
        """Report status and version; obtain and send current data"""

        config = self.actor.config
        options = config.options("address")

        channels = [channel for channel in options] if channel is None else [channel]
        for channel in channels:
            try:
                cmd.inform("%s=%s" % (channel, self.actor.getStatus(cmd, channel)))
            except Exception as e:
                cmd.warn("text='getStatus %s has failed %s'" % (channel,
                                                                self.actor.formatException(e, sys.exc_info()[2])))
        self.actor.closeSock()
        cmd.finish()


    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords
        channel = cmdKeys["channel"].values[0]

        bool = "on" if "on" in cmdKeys else "off"

        try:
            ret = self.actor.switch(cmd, channel, bool)
            self.status(cmd, channel)
        except Exception as e:
            cmd.fail("text='switch %s has failed %s'" % (channel, self.actor.formatException(e, sys.exc_info()[2])))
            self.actor.closeSock()

