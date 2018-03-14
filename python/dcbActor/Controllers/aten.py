__author__ = 'alefur'
import logging
import socket
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket
from enuActor.Controllers.device import Device
from dcbActor.Controllers.simulator.atensim import Atensim


class aten(Device):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Device.__init__(self, actor, name)

        self.sock = None
        self.simulator = None
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n>')
        self.EOL = '\r\n'

        self.state = {}

        self.actor.callCommand("%s status" % name)

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.actor.reloadConfiguration(cmd=cmd)

        self.host = self.actor.config.get('aten', 'host')
        self.port = int(self.actor.config.get('aten', 'port'))
        self.mode = self.actor.config.get('aten', 'mode')

    def startCommunication(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.simulator = Atensim() if self.mode == "simulation" else None  # Create new simulator

        s = self.connectSock()

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
            return "on" if ' on' in ret else "off"

    def getStatus(self, cmd, channels=False, doFinish=True):

        if not channels:
            config = self.actor.config
            options = config.options("address")
            channels = [channel for channel in options]

        cmd.inform('atenMode=%s'%self.mode)
        cmd.inform('atenState=%s' % self.fsm.current)

        if self.fsm.current in ['IDLE', 'BUSY']:

            for channel in channels:
                try:
                    stat = self.checkStatus(cmd, channel)
                    self.state[channel] = True if stat == "on" else False
                    cmd.inform("%s=%s" % (channel, stat))
                except Exception as e:
                    cmd.warn('text=%s' % self.actor.strTraceback(e))

            v, a, w = self.checkVaw(cmd)
            cmd.inform("aten_vaw=%s,%s,%s" % (v, a, w))

        if doFinish:
            self.closeSock()
            cmd.finish()

    def checkVaw(self, cmd):

        v = self.sendOneCommand('read meter dev volt simple', doClose=False, cmd=cmd)
        a = self.sendOneCommand('read meter dev curr simple', doClose=False, cmd=cmd)
        w = self.sendOneCommand('read meter dev pow simple', doClose=False, cmd=cmd)

        return v, a, w

    def connectSock(self, i=0):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """

        if self.sock is None:

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.mode == 'operation' else self.simulator
            s.settimeout(2.0)
            s.connect((self.host, self.port))

            time.sleep(0.1)
            msg = s.recv(1024)
            msg = msg.decode()
            if msg[-7:] != "Login: ":
                if i > 2:
                    raise Exception("weird")
                else:
                    return self.connectSock(i + 1)

            s.sendall(("teladmin%s" % self.EOL).encode())

            time.sleep(0.1)
            msg = s.recv(1024).decode()
            if msg[-10:] != "Password: ":
                if i > 2:
                    raise Exception("bad login")
                else:
                    return self.connectSock(i + 1)

            s.sendall(("pfsait%s" % self.EOL).encode())

            time.sleep(0.1)
            msg = s.recv(1024).decode()
            if "Logged in successfully" not in msg:
                if i > 2:
                    raise Exception("bad password")
                else:
                    return self.connectSock(i + 1)

            self.sock = s

        return self.sock
