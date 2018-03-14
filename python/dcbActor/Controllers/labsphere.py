import logging
import time
from datetime import datetime as dt

import enuActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from dcbActor.Controllers.labsphere_drivers import LabsphereTalk
from dcbActor.Controllers.simulator.labsim import Labspheresim
from enuActor.Controllers.device import Device


class labsphere(Device):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Device.__init__(self, actor, name)
        self.sock = None
        self.simulator = None

        self.EOL = ''
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')

        self.resetValue()

        #self.actor.callCommand("%s status" % name)

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.actor.reloadConfiguration(cmd=cmd)

        self.host = self.actor.config.get('labsphere', 'host')
        self.port = int(self.actor.config.get('labsphere', 'port'))
        self.mode = self.actor.config.get('labsphere', 'mode')

    def startCommunication(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.simulator = Labspheresim(self.actor) if self.mode == "simulation" else None  # Create new simulator
        s = self.connectSock()

    def initialise(self, cmd):
        """| Initialise the interlock board, called y device.initDevice().


        :param cmd: on going command
        :raise: Exception if a command fail, user if warned with error
        """

        labs = LabsphereTalk()
        for cmdStr, tempo in labs.init():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        for cmdStr, tempo in labs.fullOpen():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = 0

    @property
    def fluxmedian(self):
        flux = np.array([val for date, val in self.arrPhotodiode])
        fluxmedian = np.median(flux) if len(flux) > 10 else np.nan

        return fluxmedian

    def resetValue(self):

        self.attenVal = -1
        self.halogenBool = False
        self.arrPhotodiode = []

    def switchAttenuator(self, cmd, value):
        labs = LabsphereTalk()
        for cmdStr, tempo in labs.attenuator(value):
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = value

    def switchHalogen(self, cmd, bool):
        labs = LabsphereTalk()
        self.sendOneCommand(labs.setLamp(bool), doClose=False, cmd=cmd)
        self.halogenBool = bool

    def getStatus(self, cmd, doFinish=True):
        ender = cmd.finish if doFinish else cmd.inform

        cmd.inform('labsMode=%s' % self.mode)
        cmd.inform('labsState=%s' % self.fsm.current)

        if self.fsm.current in ['IDLE', 'BUSY']:
            labs = LabsphereTalk()
            flux = self.sendOneCommand(labs.photodiode(), doClose=True, cmd=cmd)
            flux = flux if flux != '' else np.nan
            self.arrPhotodiode.append((dt.now(), float(flux)))

            arrPhotodiode = [(date, val) for date, val in self.arrPhotodiode if (dt.now() - date).total_seconds() < 60]
            self.arrPhotodiode = arrPhotodiode

            cmd.inform("attenuator=%i" % self.attenVal)
            cmd.inform("halogen=%s" % ("on" if self.halogenBool else "off"))
            cmd.inform("fluxmedian=%.3f" % self.fluxmedian)
            cmd.inform("photodiode=%.3f" % float(flux))

        if doFinish:
            cmd.finish()