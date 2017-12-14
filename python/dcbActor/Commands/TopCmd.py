#!/usr/bin/env python

import subprocess

import opscore.protocols.keys as keys
import opscore.protocols.types as types


class TopCmd(object):
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
            ('status', '[@all]', self.status),
            ('connect', '<controller> [<name>]', self.connect),
            ('disconnect', '<controller>', self.disconnect),
            ('monitor', '<controllers> <period>', self.monitor),
            ('start', '', self.initControllers),
            ('halogen', '@(on|off) [<attenuator>] [force]', self.halogen),
            ('hgar', '@(on|off) [<attenuator>] [force]', self.hgar),
            ('neon', '@(on|off) [<attenuator>] [force]', self.neon),
            ('xenon', '@(on|off) [<attenuator>] [force]', self.xenon),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__dcb", (1, 1),
                                        keys.Key("name", types.String(),
                                                 help='an optional name to assign to a controller instance'),
                                        keys.Key("controllers", types.String() * (1, None),
                                                 help='the names of 1 or more controllers to load'),
                                        keys.Key("controller", types.String(),
                                                 help='the names a controller.'),
                                        keys.Key("period", types.Int(),
                                                 help='the period to sample at.'),
                                        keys.Key("arc", types.String(),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("attenuator", types.Int(),
                                                 help='Attenuator value.'),
                                        )

    def monitor(self, cmd):
        """ Enable/disable/adjust period controller monitors. """

        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values

        knownControllers = []
        for c in self.actor.config.get(self.actor.name, 'controllers').split(','):
            c = c.strip()
            knownControllers.append(c)

        foundOne = False
        for c in controllers:
            if c not in knownControllers:
                cmd.warn('text="not starting monitor for %s: unknown controller"' % (c))
                continue

            self.actor.monitor(c, period, cmd=cmd)
            foundOne = True

        if foundOne:
            cmd.finish()
        else:
            cmd.fail('text="no controllers found"')

    def controllerKey(self):
        controllerNames = self.actor.controllers.keys()
        key = 'controllers=%s' % (','.join([c for c in controllerNames]))

        return key

    def connect(self, cmd, doFinish=True):
        """ Reload all controller objects. """

        controller = cmd.cmd.keywords['controller'].values[0]
        try:
            instanceName = cmd.cmd.keywords['name'].values[0]
        except:
            instanceName = controller

        try:
            self.actor.attachController(controller,
                                        instanceName=instanceName,
                                        cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to connect controller %s: %s"' % (instanceName,
                                                                     e))
            return

        cmd.finish(self.controllerKey())

    def disconnect(self, cmd, doFinish=True):
        """ Disconnect the given, or all, controller objects. """

        controller = cmd.cmd.keywords['controller'].values[0]

        try:
            self.actor.detachController(controller)
        except Exception as e:
            cmd.fail('text="failed to disconnect controller %s: %s"' % (controller, e))
            return
        cmd.finish(self.controllerKey())

    def initControllers(self, cmd):
        for c in self.actor.controllers:
            print "c=", c
            self.actor.callCommand("%s init" % c)
        cmd.finish()

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)

        cmd.inform('text=%s' % ("Present!"))
        cmd.inform('text="monitors: %s"' % (self.actor.monitors))
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.config),
                                                   self.actor.config.sections()))
        cmd.inform("version=%s" % subprocess.check_output(["git", "describe"]))

        if 'all' in cmd.cmd.keywords:
            for c in self.actor.controllers:
                self.actor.callCommand("%s status" % (c))

        cmd.finish(self.controllerKey())

    def halogen(self, cmd):
        cmdKeys = cmd.cmd.keywords

        arc = 'halogen'
        switchOn = True if "on" in cmdKeys else False
        force = True if 'force' in cmdKeys else False
        attenVal = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else None

        self.actor.switchArc(cmd, arc, switchOn, attenVal, force)

    def hgar(self, cmd):
        cmdKeys = cmd.cmd.keywords

        arc = 'hgar'
        switchOn = True if "on" in cmdKeys else False
        force = True if 'force' in cmdKeys else False
        attenVal = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else None

        self.actor.switchArc(cmd, arc, switchOn, attenVal, force)

    def neon(self, cmd):
        cmdKeys = cmd.cmd.keywords

        arc = 'ne'
        switchOn = True if "on" in cmdKeys else False
        force = True if 'force' in cmdKeys else False
        attenVal = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else None

        self.actor.switchArc(cmd, arc, switchOn, attenVal, force)

    def xenon(self, cmd):
        cmdKeys = cmd.cmd.keywords

        arc = 'xenon'
        switchOn = True if "on" in cmdKeys else False
        force = True if 'force' in cmdKeys else False
        attenVal = cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else None

        self.actor.switchArc(cmd, arc, switchOn, attenVal, force)