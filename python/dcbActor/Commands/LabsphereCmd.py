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
            ('arc', '[<on>] [<off>] [<attenuator>] [force]', self.switch),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb_labsphere", (1, 1),
                                        keys.Key("channel", types.String(), help="which channel to power on"),
                                        keys.Key("attenuator", types.Int(), help="attenuator value"),
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

        self.controller.generate(cmd)

    @threaded
    def moveAttenuator(self, cmd):
        cmdKeys = cmd.cmd.keywords

        value = cmdKeys['attenuator'].values[0]
        if value != self.controller.attenuator:
            self.controller.substates.move(cmd, value)
        self.controller.generate(cmd)

    @threaded
    def initialise(self, cmd):

        self.controller.substates.init(cmd)
        self.controller.generate(cmd)

    @threaded
    def switchHalogen(self, cmd):
        cmdKeys = cmd.cmd.keywords

        state = 'on' if 'on' in cmdKeys else 'off'

        self.controller.substates.halogen(cmd, state)
        self.controller.generate(cmd)

    @threaded
    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords

        arcOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        arcOff = cmdKeys['off'].values if 'off' in cmdKeys else []

        force = True if 'force' in cmdKeys else False
        attenuator = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else None

        for arc in arcOn + arcOff:
            if arc not in self.actor.arcs.keys():
                raise KeyError('%s is unknown' % arc)

        switchOn = [(arc, 'on') for arc in arcOn if self.actor.arcs[arc] != 'on']
        switchOff = [(arc, 'off') for arc in arcOff if self.actor.arcs[arc] != 'off']

        if switchOn:
            attenuator = self.controller.attenuator if attenuator is None else attenuator
        else:
            force = True

        if force:
            attenuator = None if attenuator == self.controller.attenuator else attenuator

        effectiveSwitch = dict(switchOff + switchOn)

        halogen = effectiveSwitch.pop('halogen', None)
        atenOn = [arc for arc, state in effectiveSwitch.items() if state == 'on']
        atenOff = [arc for arc, state in effectiveSwitch.items() if state == 'off']

        self.controller.arc(cmd=cmd,
                            atenOn=atenOn,
                            atenOff=atenOff,
                            halogen=halogen,
                            force=force,
                            attenuator=attenuator)

        cmd.finish()
