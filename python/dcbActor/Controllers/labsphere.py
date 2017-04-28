import logging
import socket
import time
from datetime import datetime as dt

import dcbActor.Controllers.bufferedSocket as bufferedSocket
import numpy as np
from dcbActor.Controllers.device import Device
from dcbActor.Controllers.labsphere_drivers import LabsphereTalk


class labsphere(Device):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Device.__init__(self, actor, name)

        self.EOL = ''
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')
        self.sock = None

        self.host = self.actor.config.get('labsphere', 'host')
        self.port = int(self.actor.config.get('labsphere', 'port'))

        self.resetValue()

        self.actor.callCommand("%s status" % name)

    def resetValue(self):

        self.attenVal = -1
        self.halogenBool = False
        self.arrPhotodiode = []

    def switchAttenuator(self, cmd, value):
        labs = LabsphereTalk()
        for cmdStr, tempo in labs.Attenuator(value):
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = value

    def switchHalogen(self, cmd, bool):
        labs = LabsphereTalk()
        self.sendOneCommand(labs.Lamp(bool), doClose=False, cmd=cmd)
        self.halogenBool = bool

    def getStatus(self, cmd, doFinish=False):
        ender = cmd.finish if doFinish else cmd.inform

        labs = LabsphereTalk()
        flux = self.sendOneCommand(labs.Read_Photodiode(), doClose=True, cmd=cmd)
        flux = flux if flux != '' else np.nan
        self.arrPhotodiode.append((dt.now(), float(flux)))

        arrPhotodiode = [(date, val) for date, val in self.arrPhotodiode if (dt.now() - date).total_seconds() < 60]
        self.arrPhotodiode = arrPhotodiode

        cmd.inform("attenuator=%i" % self.attenVal)
        cmd.inform("halogen=%s" % ("on" if self.halogenBool else "off"))
        ender("photodiode=%.3f" % float(flux))

    def initialise(self, cmd):
        labs = LabsphereTalk()
        for cmdStr, tempo in labs.LabSphere_init():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

        self.attenVal = 0

    def connectSock(self):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """

        if self.sock is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
            except Exception as e:
                raise Exception("%s failed to create socket : %s" % (self.name, self.formatException(e)))

            try:
                s.connect((self.host, self.port))

            except Exception as e:
                raise Exception("%s failed to connect socket : %s" % (self.name, self.formatException(e)))

            self.sock = s

        return self.sock
