import time
import logging
import numpy as np
import dcbActor.Controllers.labsphere_drivers as labs
import enuActor.Controllers.bufferedSocket as bufferedSocket

from dcbActor.Controllers.simulator.labsim import Labspheresim
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread


class labsphere(FSMDev, QThread, bufferedSocket.EthComm):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')
        self.EOL = ''
        self.sock = None

        self.mode = ''
        self.sim = None

        self.resetValue()

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def fluxmedian(self):
        flux = np.array([val for date, val in self.arrPhotodiode])
        fluxmedian = np.median(flux) if len(flux) > 10 else np.nan

        return fluxmedian

    def resetValue(self):

        self.attenVal = -1
        self.halogenOn = False
        self.arrPhotodiode = []

    def start(self, cmd=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd)

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)
        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        try:
            self.actor._reloadConfiguration(cmd=cmd)
        except RuntimeError:
            pass

        self.host = self.actor.config.get('labsphere', 'host')
        self.port = int(self.actor.config.get('labsphere', 'port'))
        self.mode = self.actor.config.get('labsphere', 'mode')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sock = Labspheresim(self.actor) if self.mode == "simulation" else None  # Create new simulator
        s = self.connectSock()

    def init(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().


        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        for cmdStr, tempo in labs.init():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        for cmdStr, tempo in labs.fullOpen():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = 0

    def switchAttenuator(self, cmd, value):

        for cmdStr, tempo in labs.attenuator(value):
            self.sendOneCommand(cmdStr, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = value

    def switchHalogen(self, cmd, bool):

        self.sendOneCommand(labs.setLamp(bool), cmd=cmd)
        self.halogenOn = bool
        cmd.inform("halogen=%s" % ("on" if self.halogenOn else "off"))

    def getStatus(self, cmd):

        cmd.inform('labsMode=%s' % self.mode)

        # self.actor.getState(cmd)
        if self.states.current == 'ONLINE':
            flux = self.photodiode(cmd=cmd)

            cmd.inform("attenuator=%i" % self.attenVal)
            cmd.inform("halogen=%s" % ("on" if self.halogenOn else "off"))
            cmd.inform("fluxmedian=%.3f" % self.fluxmedian)
            cmd.inform("photodiode=%.3f" % float(flux))

        cmd.finish()

    def photodiode(self, cmd):
        flux = self.sendOneCommand(labs.photodiode(), cmd=cmd)
        flux = flux if flux != '' else np.nan
        self.arrPhotodiode.append((time.time(), float(flux)))

        arrPhotodiode = [(date, val) for date, val in self.arrPhotodiode if (time.time() - date) < 60]
        self.arrPhotodiode = arrPhotodiode
        return flux

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
