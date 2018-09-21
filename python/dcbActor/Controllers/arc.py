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
                "halogen": self.controllers["labsphere"].halogenOn}

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
        self.actor.callCommand('monitor controllers=labsphere period=5')

        try:
            cmdSwitch = [(arc, True) for arc in e.switchOn] + [(arc, False) for arc in e.switchOff]
            effectiveSwitch = dict([(arc, bool) for arc, bool in cmdSwitch if self.state[arc] != bool])

            if not effectiveSwitch:
                force = True
            else:
                halogen = effectiveSwitch.pop('halogen', None)
                if halogen is not None:
                    state = 'on' if halogen else 'off'
                    self.controllers["labsphere"].substates.halogen(cmd=e.cmd, state=state)

                switchOn = [arc for arc, bool in effectiveSwitch.items() if bool]
                switchOff = [arc for arc, bool in effectiveSwitch.items() if not bool]

                self.controllers["aten"].substates.switch(cmd=e.cmd, switchOn=switchOn, switchOff=switchOff)

            if not force:
                self.flux.clear()
                while not self.flux.isCompleted:
                    time.sleep(1)

                start = time.time()
                while not (self.flux.mean > 0.001) and (self.flux.std < 0.05):
                    time.sleep(1)
                    if (time.time() - start) > 120:
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
