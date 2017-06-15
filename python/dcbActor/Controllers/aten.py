__author__ = 'alefur'
import logging
import socket
import sys
import time

import dcbActor.Controllers.bufferedSocket as bufferedSocket
from dcbActor.Controllers.device import Device


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
        self.state = {}

        self.actor.callCommand("%s status" % name)

    def switch(self, cmd, channel, bool):
        bool = 'on' if bool else 'off'
        address = self.actor.config.get('address', channel)
        return self.sendOneCommand("sw o%s %s imme" % (address.zfill(2), bool), doClose=False, cmd=cmd)

    def checkStatus(self, cmd, channel):

        address = self.actor.config.get('address', channel)
        ret = self.sendOneCommand("read status o%s format" % address.zfill(2), doClose=False, cmd=cmd)

        if "pending" in ret:
            time.sleep(1)
            return self.checkStatus(cmd, channel)
        else:
            return "on" if ' on' in ret.split('\r\n')[1] else "off"

    def getStatus(self, cmd, channels, doClose=False):
        for channel in channels:
            try:
                stat = self.checkStatus(cmd, channel)
                self.state[channel] = True if stat == "on" else False
                cmd.inform("%s=%s" % (channel, stat))
            except Exception as e:
                cmd.warn("text='checkStatus %s has failed %s'" % (channel, self.formatException(e, sys.exc_info()[2])))

        v, a, w = self.checkVaw(cmd)
        cmd.inform("aten_vaw=%s,%s,%s" % (v, a, w))
        if doClose:
            self.closeSock()

    def checkVaw(self, cmd):

        v = self.sendOneCommand('read meter dev volt simple', doClose=False, cmd=cmd)
        a = self.sendOneCommand('read meter dev curr simple', doClose=False, cmd=cmd)
        w = self.sendOneCommand('read meter dev pow simple', doClose=False, cmd=cmd)

        return v.split('\r\n')[1].strip(), a.split('\r\n')[1].strip(), w.split('\r\n')[1].strip()

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
