import logging
import time

from actorcore.FSM import FSMDev
from actorcore.QThread import QThread


class arc(FSMDev, QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        substates = ['IDLE', 'WARMING', 'FAILED']
        events = [{'name': 'warmup', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['WARMING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['WARMING'], 'dst': 'FAILED'},
                  ]
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)
        self.addStateCB('WARMING', self.switchArc)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.defaultSamptime = 0

    @property
    def controllers(self):
        return self.actor.controllers

    @property
    def state(self):
        return {"neon": self.controllers["aten"].state["neon"],
                "hgar": self.controllers["aten"].state["hgar"],
                "xenon": self.controllers["aten"].state["xenon"],
                "krypton": self.controllers["aten"].state["krypton"],
                "halogen": self.controllers["labsphere"].halogen}

    @property
    def flux(self):
        return self.controllers["labsphere"].smoothFlux

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def switchArc(self, e):
        force = True if not e.switchOn else e.force
        self.actor.callCommand('monitor controllers=labsphere period=3')

        try:
            cmdSwitch = [(arc, 'on') for arc in e.switchOn] + [(arc, 'off') for arc in e.switchOff]
            effectiveSwitch = dict([(arc, state) for arc, state in cmdSwitch if self.state[arc] != state])

            if not effectiveSwitch:
                force = True
            else:
                halogen = effectiveSwitch.pop('halogen', None)
                if halogen is not None:
                    self.actor.callCommand('labsphere halogen %s' % halogen)

                switchOn = [arc for arc, state in effectiveSwitch.items() if state == 'on']
                switchOff = [arc for arc, state in effectiveSwitch.items() if state == 'off']

                if switchOn or switchOff:
                    self.actor.callCommand('power %s %s' % ('on=%s' % ','.join(switchOn) if switchOn else '',
                                                            'off=%s' % ','.join(switchOff) if switchOff else ''))

            if not force:
                self.flux.clear()

                while not self.flux.isCompleted:
                    time.sleep(0.1)

                start = time.time()
                while not (self.flux.median > 0.01) and (self.flux.std < 0.5):
                    time.sleep(0.1)
                    if (time.time() - start) > 150:
                        raise TimeoutError('Photodiode flux is null or unstable')

            self.substates.idle(cmd=e.cmd)

        except:
            self.substates.fail(cmd=e.cmd)
            raise

        finally:
            self.actor.callCommand('monitor controllers=labsphere period=15')

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
