#!/usr/bin/env python


import configparser

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
            ('status', '[@all] [<controllers>]', self.status),
            ('monitor', '<controllers> <period>', self.monitor),
            ('set', '<controller> <mode>', self.changeMode),
            ('config', '<fibers>', self.configFibers)
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
                                        keys.Key("mode", types.String(),
                                                 help='controller mode'),
                                        keys.Key("fibers", types.String() * (1, None),
                                                 help='the names of current fiber bundles'),
                                        )

    def monitor(self, cmd):
        """ Enable/disable/adjust period controller monitors. """
        cmdKeys = cmd.cmd.keywords
        period = cmdKeys['period'].values[0]
        controllers = cmdKeys['controllers'].values

        knownControllers = []
        for c in self.actor.config.get(self.actor.name, 'controllers').split(','):
            c = c.strip()
            knownControllers.append(c)

        knownControllers = [c.strip() for c in self.actor.config.get(self.actor.name, 'controllers').split(',')]

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
        controllerNames = list(self.actor.controllers.keys())
        key = 'controllers=%s' % (','.join([c for c in controllerNames]))

        return key

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords
        self.actor.sendVersionKey(cmd)

        cmd.inform('text=%s' % ("Present!"))
        cmd.inform('text="monitors: %s"' % (self.actor.monitors))
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.config),
                                                   self.actor.config.sections()))

        self.actor.updateStates(cmd=cmd)
        self.actor.pfsDesignId(cmd=cmd)

        if 'all' in cmdKeys:
            for controller in self.actor.controllers:
                self.actor.callCommand("%s status" % controller)
        if 'controllers' in cmdKeys:
            for controller in cmdKeys['controllers'].values:
                self.actor.callCommand("%s status" % controller)

        cmd.finish(self.controllerKey())

    def changeMode(self, cmd):
        """Change device mode operation|simulation"""
        cmdKeys = cmd.cmd.keywords

        controller = cmdKeys['controller'].values[0]
        mode = cmdKeys['mode'].values[0]

        knownControllers = [c.strip() for c in self.actor.config.get(self.actor.name, 'controllers').split(',')]

        if controller not in knownControllers:
            raise ValueError('unknown controller')

        if mode not in ['operation', 'simulation']:
            raise ValueError('unknown mode')

        self.actor.attachController(name=controller,
                                    cmd=cmd,
                                    mode=mode)

        self.actor.callCommand("%s status" % controller)

        cmd.finish()

    def configFibers(self, cmd):
        cmdKeys = cmd.cmd.keywords
        fibers = cmdKeys['fibers'].values

        conf = configparser.ConfigParser()
        conf.read_file(open('/software/ait/fiberConfig.cfg'))
        strFibers = ','.join([fib.strip() for fib in fibers])
        conf.set('current', 'fibers', strFibers)
        conf.write(open('/software/ait/fiberConfig.cfg', 'w'))
        self.actor.pfsDesignId(cmd=cmd)

        cmd.finish()


