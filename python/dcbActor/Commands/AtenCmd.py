#!/usr/bin/env python

import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from dcbActor.wrap import threaded


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
            (self.name, '@(switch) @(on|off) @(<channel>|<channels>)', self.switch),
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

        config = self.actor.config
        options = config.options("address")

        channels = [channel for channel in options]

        self.controller.getStatus(cmd, channels, doClose=True)

        cmd.finish()

    @threaded
    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords

        if "channels" in cmdKeys:
            channels = cmdKeys["channels"].values
        else:
            channels = [cmdKeys["channel"].values[0]]

        bool = True if "on" in cmdKeys else False

        for channel in channels:
            try:
                ret = self.controller.switch(cmd, channel, bool)

            except Exception as e:
                cmd.fail(
                    "text='switch %s has failed %s'" % (channel, self.controller.formatException(e, sys.exc_info()[2])))
                self.controller.closeSock()
                return

        self.controller.getStatus(cmd, channels, doClose=True)

        cmd.finish()
        if channels == ["pow_attenuator", "pow_sphere", "pow_halogen"]:
            try:
                self.actor.controllers['labsphere'].resetValue()
            except:
                pass
