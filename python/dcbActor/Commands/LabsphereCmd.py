#!/usr/bin/env python

import sys

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from dcbActor.wrap import threaded


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
            (self.name, 'ping', self.ping),
            (self.name, 'status', self.status),
            (self.name, '<value>', self.switchAttenuator),
            (self.name, '@(switch) @(on|off)', self.switchHalogen),
            (self.name, 'init', self.initialise),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb_labsphere", (1, 1),
                                        keys.Key("channel", types.String(), help="which channel to power on"),
                                        keys.Key("value", types.Int(), help="attenuator value"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.finish("text='Present and (probably) well'")

    @threaded
    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        try:
            self.controller.getStatus(cmd, doFinish=True)

        except Exception as e:
            cmd.warn(
                "text='get photodiode value has failed %s'" % (self.controller.formatException(e, sys.exc_info()[2])))
            val = np.nan
            self.controller.closeSock()



    def switchAttenuator(self, cmd):
        cmdKeys = cmd.cmd.keywords

        value = cmdKeys['value'].values[0]

        try:
            ret = self.controller.switchAttenuator(cmd, value)

            self.status(cmd)
        except Exception as e:
            cmd.fail("text='switch attenuator has failed %s'" % (self.controller.formatException(e, sys.exc_info()[2])))
            self.controller.closeSock()

    def initialise(self, cmd):
        try:
            ret = self.controller.initialise(cmd)
            self.status(cmd)
        except Exception as e:
            cmd.fail(
                "text='initialise labsphere has failed %s'" % (self.controller.formatException(e, sys.exc_info()[2])))
            self.controller.closeSock()

    def switchHalogen(self, cmd):
        cmdKeys = cmd.cmd.keywords

        bool = True if 'on' in cmdKeys else False

        try:
            ret = self.controller.switchHalogen(cmd, bool)

            self.status(cmd)
        except Exception as e:
            cmd.fail("text='switch halogen has failed %s'" % (self.controller.formatException(e, sys.exc_info()[2])))
            self.controller.closeSock()
