import logging
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
import time


class arc(FSMDev,QThread):
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
        return self.controllers["labsphere"].flux

    def start(self, cmd=None, doInit=True):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def switchArc(self, e):
        force = True if not e.switchOn else e.force

        try:
            nextState = self.state
            toSwitch = [(arc, True) for arc in e.switchOn] + [(arc, False) for arc in e.switchOff]

            for arc, bool in toSwitch:
                if arc not in nextState.keys():
                    raise KeyError('unknown arc lamp')
                nextState[arc] = bool

            if self.state != nextState:

                for arc, bool in toSwitch:
                    if arc in ['neon', 'hgar', 'xenon', 'krypton']:
                        self.controllers["aten"].switch(cmd=e.cmd, channel=arc, bool=bool)
                    else:
                        self.controllers["labsphere"].substates.halogen(cmd=e.cmd, bool=bool)

                if not force:
                    self.flux.clear()
                    while not self.flux.isWarmedUp:
                        time.sleep(5)

                    start = time.time()
                    while not (self.flux.mean > 0.001) and (self.flux.std < 0.05):
                        time.sleep(5)
                        if (time.time() - start) > 300:
                            raise Exception('Timeout photodiode flux is null or unstable')

            self.substates.idle(cmd=e.cmd)
        except:
            self.substates.fail(cmd=e.cmd)
            raise


    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()