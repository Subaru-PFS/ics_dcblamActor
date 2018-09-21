import logging
import time

import dcbActor.Controllers.labsphere_drivers as labsDrivers
import enuActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.labsphere import Labspheresim


class SmoothFlux(list):
    def __init__(self):
        list.__init__(self)

    @property
    def values(self):
        return np.array([val for date, val in self])

    @property
    def median(self):
        return np.median(self.values)

    @property
    def mean(self):
        return np.mean(self.values)

    @property
    def std(self):
        return np.std(self.values)

    @property
    def isCompleted(self):
        return len(self) > 8

    def append(self, object):
        list.append(self, object)
        self.smoothOut()

    def smoothOut(self, outdated=60):
        i = 0
        while i < len(self):
            if (time.time() - self[i][0]) > outdated:
                self.remove((self[i]))
            else:
                i += 1


class labsphere(FSMDev, QThread, bufferedSocket.EthComm):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        substates = ['IDLE', 'MOVING', 'WARMING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'halogen', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['MOVING', 'WARMING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', 'WARMING'], 'dst': 'FAILED'},
                  ]

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name, timeout=4)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moveAttenuator)
        self.addStateCB('WARMING', self.switchHalogen)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n', timeout=1.0)
        self.EOL = ''
        self.sock = None

        self.mode = ''
        self.sim = None

        self.smoothFlux = SmoothFlux()
        self.attenuator = -1
        self.halogen = 'undef'

        self.defaultSamptime = 15

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def halogenOn(self):
        return self.halogen == 'on'

    def start(self, cmd=None, doInit=False, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

        try:
            self.actor.attachController(name='arc')
        except Exception as e:
            cmd.warn('text="%s' % self.actor.strTraceback(e))

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)

        try:
            self.actor.detachController(controllerName='arc')
        except Exception as e:
            cmd.warn('text="%s' % self.actor.strTraceback(e))

        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.host = self.actor.config.get('labsphere', 'host')
        self.port = int(self.actor.config.get('labsphere', 'port'))
        self.mode = self.actor.config.get('labsphere', 'mode') if mode is None else mode

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('labsMode=%s' % self.mode)
        self.sim = Labspheresim(self.actor)
        s = self.connectSock()
        flux = self.photodiode(cmd=cmd)

    def init(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().


        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        for cmdStr in labsDrivers.init():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)

        for cmdStr in labsDrivers.fullClose():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)

        self.sendOneCommand(labsDrivers.turnQth(state='off'), doClose=False, cmd=cmd)

        self.attenuator = 255
        self.halogen = 'off'

    def moveAttenuator(self, e):

        try:
            for cmdStr in labsDrivers.attenuator(e.value):
                self.sendOneCommand(cmdStr, cmd=e.cmd)

            self.attenuator = e.value
            self.substates.idle(cmd=e.cmd)

        except:

            self.substates.fail(cmd=e.cmd)
            self.attenuator = -1
            raise

    def switchHalogen(self, e):
        try:
            self.sendOneCommand(labsDrivers.turnQth(state=e.state), cmd=e.cmd)
            state = 'on' if e.bool else 'off'
            self.halogen = state
            self.substates.idle(cmd=e.cmd)
            e.cmd.inform('halogen=%s' % self.halogen)
        except:
            self.halogen = 'undef'
            self.substates.fail(cmd=e.cmd)
            raise

    def getStatus(self, cmd):
        cmd.inform('labsphereFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('labsphereMode=%s' % self.mode)

        if self.states.current in ['LOADED', 'ONLINE']:

            try:
                self.flux = self.photodiode(cmd=cmd)

            except:
                self.flux = np.nan
                self.smoothFlux.clear()
                raise

            finally:
                cmd.inform('attenuator=%i' % self.attenuator)
                cmd.inform('halogen=%s' % self.halogen)
                cmd.inform('fluxmedian=%.3f' % self.smoothFlux.median)
                cmd.inform('photodiode=%.3f' % self.flux)

        cmd.finish()

    def photodiode(self, cmd):
        footLamberts = self.sendOneCommand(labsDrivers.photodiode(), cmd=cmd)
        flux = np.round(float(footLamberts) * 3.426, 3)

        self.smoothFlux.append((time.time(), flux))

        return flux

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def sendOneCommand(self, *args, **kwargs):
        if self.actor.controllers['aten'].pow_labsphere != 'on':
            raise UserWarning('labsphere is not powered on')

        return bufferedSocket.EthComm.sendOneCommand(self, *args, **kwargs)

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
