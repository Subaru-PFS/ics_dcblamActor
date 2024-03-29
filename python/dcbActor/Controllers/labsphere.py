import logging
import time

import dcbActor.Controllers.labsphere_drivers as labsDrivers
import enuActor.utils.bufferedSocket as bufferedSocket
import numpy as np
from dcbActor.Simulators.labsphere import Labspheresim
from enuActor.utils.fsmThread import FSMThread


class SmoothFlux(object):
    def __init__(self):
        object.__init__(self)
        self.current = []

    @property
    def last(self):
        return self.values[-1] if self.values.size else np.nan

    @property
    def values(self):
        values = np.array([val for time, val in self.current])
        return values[~np.isnan(values)]

    @property
    def median(self):
        median = np.median(self.values) if self.isCompleted else np.nan
        return median

    @property
    def mean(self):
        mean = np.mean(self.values) if self.isCompleted else np.nan
        return mean

    @property
    def std(self):
        std = np.std(self.values) if self.isCompleted else np.nan
        return std

    @property
    def minStd(self):
        minStd = self.median * 0.02
        minStd = 0.002 if minStd < 0.002 else minStd
        return minStd

    @property
    def isCompleted(self):
        return len(self.values) >= 8

    def new(self, value):
        """Max flux measured is 110 with Qth"""
        value = value if -0.005 < value < 130 else np.nan
        self.current.append((time.time(), value))
        self.smoothOut()

    def smoothOut(self, outdated=30):
        self.current = self.current[-9:]

    def clear(self):
        self.current.clear()


class labsphere(FSMThread, bufferedSocket.EthComm):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        substates = ['IDLE', 'MOVING', 'SWITCHING', 'WARMING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'halogen', 'src': 'IDLE', 'dst': 'SWITCHING'},
                  {'name': 'warmup', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['MOVING', 'SWITCHING', 'WARMING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', 'SWITCHING', 'WARMING'], 'dst': 'FAILED'},
                  ]
        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('MOVING', self.moveAttenuator)
        self.addStateCB('SWITCHING', self.switchHalogen)
        self.addStateCB('WARMING', self.stabFlux)
        self.sim = Labspheresim(self.actor)

        self.flux = SmoothFlux()
        self.attenuator = -1
        self.halogen = 'undef'
        self.monitor = 15

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def persistHalogen(self, cmd, state):
        self.halogen = state
        cmd.inform('halogen=%s' % state)

    def persistAttenuator(self, cmd, value):
        self.attenuator = value
        cmd.inform('attenuator=%i' % value)

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.mode = self.actor.config.get('labsphere', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('labsphere', 'host'),
                                        port=int(self.actor.config.get('labsphere', 'port')),
                                        EOL='')

    def _openComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n', timeout=1.0)
        self.connectSock()

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: RuntimeError if the communication has failed with the controller
        """
        self.checkPhotodiode(cmd, doRaise=True)
        self.persistHalogen(cmd=cmd, state='undef')
        self.persistAttenuator(cmd=cmd, value=-1)

    def _init(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().


        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """
        for cmdStr in labsDrivers.init():
            self.sendOneCommand(cmdStr, cmd=cmd)

        for cmdStr in labsDrivers.fullClose():
            self.sendOneCommand(cmdStr, cmd=cmd)

        self.sendOneCommand(labsDrivers.turnQth(state='off'), cmd=cmd)

        self.persistHalogen(cmd=cmd, state='off')
        self.persistAttenuator(cmd=cmd, value=255)

    def getStatus(self, cmd):
        self.checkPhotodiode(cmd=cmd)

    def moveAttenuator(self, cmd, value):
        tempo = 3 + abs(value - self.attenuator) * 9 / 255

        for cmdStr in labsDrivers.attenuator(value):
            self.sendOneCommand(cmdStr, cmd=cmd)

        tlim = time.time() + tempo

        while time.time() < tlim:
            self.checkPhotodiode(cmd=cmd)
            remainingTime = tlim - time.time()

            if remainingTime > 0:
                sleepTime = 2 if remainingTime > 2 else remainingTime
                time.sleep(sleepTime)

        self.persistAttenuator(cmd=cmd, value=value)

    def switchHalogen(self, cmd, state):

        self.sendOneCommand(labsDrivers.turnQth(state=state), cmd=cmd)
        self.persistHalogen(cmd=cmd, state=state)

    def checkPhotodiode(self, cmd, doRaise=False):
        flux = np.nan
        try:
            flux = self.photodiode(cmd=cmd)

        except Exception as e:
            if doRaise:
                raise
            else:
                cmd.warn('text=%s' % self.actor.strTraceback(e))
        finally:
            self.flux.new(flux)
            cmd.inform('flux=%.3f,%.3f' % (self.flux.median, self.flux.std))
            cmd.inform('photodiode=%.3f' % self.flux.last)

    def arc(self, cmd, atenOn, atenOff, halogen, force, attenuator):
        try:
            if halogen is not None:
                self.substates.halogen(cmd, halogen)

            powerOn = 'on=%s' % ','.join(atenOn) if atenOn else ''
            powerOff = 'off=%s' % ','.join(atenOff) if atenOff else ''

            if powerOn or powerOff:
                cmdVar = self.actor.cmdr.call(actor=self.actor.name,
                                              cmdStr='power %s %s' % (powerOn, powerOff),
                                              forUserCmd=cmd,
                                              timeLim=60)

            if not force:
                self.substates.move(cmd, 0)
                self.substates.warmup(cmd)

        finally:
            if attenuator is not None:
                self.substates.move(cmd, attenuator)

    def stabFlux(self, cmd):
        start = time.time()
        self.flux.clear()

        while not self.flux.isCompleted or not (self.flux.median > 0.01 and self.flux.std < self.flux.minStd):

            self.checkPhotodiode(cmd=cmd)
            time.sleep(3)

            if (time.time() - start) > 300:
                raise UserWarning('Photodiode flux is null or unstable')

            if self.exitASAP:
                raise SystemExit()

    def photodiode(self, cmd, niter=0):
        try:
            footLamberts = self.sendOneCommand(labsDrivers.photodiode(), cmd=cmd)
            return np.round(float(footLamberts) * 3.42626, 3)
        except ValueError:
            if niter > 5:
                raise
            time.sleep(1)
            return self.photodiode(cmd=cmd, niter=niter + 1)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)
        return s
