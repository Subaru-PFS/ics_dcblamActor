import logging
import socket
import time

import dcbActor.Controllers.bufferedSocket as bufferedSocket
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

    def switchAttenuator(self, cmd, value):
        labs = LabsphereTalk()
        for cmdStr, tempo in labs.Attenuator(value):
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

    def switchHalogen(self, cmd, bool):
        labs = LabsphereTalk()
        self.sendOneCommand(labs.Lamp(bool), doClose=False, cmd=cmd)

    def getStatus(self, cmd):
        labs = LabsphereTalk()
        return self.sendOneCommand(labs.Read_Photodiode(), doClose=True, cmd=cmd)

    def initialise(self, cmd):
        labs = LabsphereTalk()
        for cmdStr, tempo in labs.LabSphere_init():
            self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)
            time.sleep(tempo)

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
