__author__ = 'alefur'
import logging
import time
import dcbActor.Controllers.bufferedSocket as bufferedSocket
from dcbActor.Controllers.device import Device
import socket

class aten(Device):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Device.__init__(self, actor, name)


        self.sock = None
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n>')
        self.EOL = '\r\n'

        self.host = self.actor.config.get('aten', 'host')
        self.port = int(self.actor.config.get('aten', 'port'))

    def switch(self, cmd, channel, bool):

        address = self.actor.config.get('address', channel)
        return self.sendOneCommand("sw o%s %s imme" % (address.zfill(2), bool), doClose=False, cmd=cmd)

    def getStatus(self, cmd, channel):

        address = self.actor.config.get('address', channel)
        ret = self.sendOneCommand("read status o%s format" % address.zfill(2), doClose=False, cmd=cmd)

        if "pending" in ret:
            time.sleep(1)
            return self.getStatus(cmd, channel)
        else:
            return "on" if ' on' in ret.split('\r\n')[1] else "off"


    def connectSock(self, i=0):
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
                time.sleep(0.1)
                if s.recv(1024)[-7:] != "Login: ":
                    if i > 2:
                        raise Exception("weird")
                    else:
                        return self.connectSock(i + 1)
                s.send("teladmin%s" % self.EOL)
                time.sleep(0.1)
                if s.recv(1024)[-10:] != "Password: ":
                    if i > 2:
                        raise Exception("bad login")
                    else:
                        return self.connectSock(i + 1)
                s.send("pfsait%s" % self.EOL)
                time.sleep(0.1)
                if "Logged in successfully" not in s.recv(1024):
                    if i > 2:
                        raise Exception("bad password")
                    else:
                        return self.connectSock(i + 1)

            except Exception as e:
                raise Exception("%s failed to connect socket : %s" % (self.name, self.formatException(e)))

            self.sock = s

        return self.sock