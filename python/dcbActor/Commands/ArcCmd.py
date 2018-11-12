#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class ArcCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = 'arc'
        self.vocab = [
            ('arc', '[<on>] [<off>] [<attenuator>] [force]', self.switch),
            ('arc', 'status', self.status)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__arc", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(),
                                                 help='Attenuator value.'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['arc']
        except KeyError:
            raise RuntimeError('arc controller is not connected.')

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        cmd.finish()

    @threaded
    def switch(self, cmd):
        cmdKeys = cmd.cmd.keywords

        switchOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        switchOff = cmdKeys['off'].values if 'off' in cmdKeys else []

        force = True if 'force' in cmdKeys else False
        attenuator = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else False

        for channel in switchOn + switchOff:
            self.actor.controllers['aten'].getOutlet(channel=channel)

        if attenuator and attenuator != self.actor.controllers['labsphere'].attenuator:
            self.actor.controllers['labsphere'].substates.move(cmd=cmd, value=attenuator)

        self.controller.substates.warmup(cmd=cmd,
                                         switchOn=switchOn,
                                         switchOff=switchOff,
                                         force=force)
        cmd.finish()
