#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, blocking, singleShot

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
            (self.name, 'stop', self.stop),
            (self.name, 'start [@(operation|simulation)]', self.start),

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

        self.controller.generate(cmd)

    @blocking
    def initialise(self, cmd):
        """Initialise Bsh, call fsm startInit event """

        self.controller.substates.init(cmd)
        self.controller.generate(cmd)

    @blocking
    def cmdShutter(self, cmd):
        """Open/close , optional keyword force to force transition (without breaking interlock)"""
        cmdKeys = cmd.cmd.keywords

        if "open" in cmdKeys:
            self.controller.substates.openshutter(cmd)
        else:
            self.controller.substates.closeshutter(cmd)

        self.controller.generate(cmd)

    @blocking
    def setGrating(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        gratingId = int(cmdKeys["grating"].values[0])
        self.controller.substates.setgrating(cmd, gratingId)
        self.controller.generate(cmd)

    @blocking
    def setOutport(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        outportId = int(cmdKeys["outport"].values[0])

        self.controller.setOutport(cmd=cmd, outportId=outportId)
        self.controller.generate(cmd)

    @blocking
    def setWave(self, cmd):
        """Update bia parameters """

        cmdKeys = cmd.cmd.keywords
        wavelength = float(cmdKeys["wave"].values[0])

        self.controller.setWave(cmd=cmd, wavelength=wavelength)
        self.controller.generate(cmd)

    @singleShot
    def stop(self, cmd):
        """ stop current motion, save hexapod position, power off hxp controller and disconnect"""
        self.actor.disconnect('mono', cmd=cmd)
        self.actor.disconnect('monoqth', cmd=cmd)

        cmd.inform('text="powering down mono controller ..."')
        self.actor.ownCall(cmd, cmdStr='power off=mono', failMsg='failed to power off mono controller')

        cmd.finish()

    @singleShot
    def start(self, cmd):
        """ power on hxp controller, connect mono controller, and init"""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('mono', 'mode')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        cmd.inform('text="powering up mono controller ..."')
        self.actor.ownCall(cmd, cmdStr='power on=mono', failMsg='failed to power on mono controller')

        if mode == 'operation':
            cmd.inform('text="waiting for tcp server ..."')
            waitForTcpServer(host=self.actor.config.get('mono', 'host'),
                             port=self.actor.config.get('mono', 'port'))

        self.actor.connect('mono', cmd=cmd, mode=mode)

        cmd.inform('text="mono init ..."')
        self.actor.ownCall(cmd, cmdStr='mono init', failMsg='failed to init mono')

        self.actor.connect('monoqth', cmd=cmd, mode=mode)

        self.controller.generate(cmd)
