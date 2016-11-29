#!/usr/bin/env python

import socket
import time
from datetime import datetime as dt
import dcbActor.bufferedSocket as bufferedSocket
from actorcore.Actor import Actor


class DcbActor(Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.initOk = 0
        Actor.__init__(self, name,
                       productName=productName,
                       configFile=configFile)
        self.sock = None
        self.tcpHost = self.config.get(name, 'tcp_host')
        self.tcpPort = int(self.config.get(name, 'tcp_port'))
        self.EOL = '\r\n'
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n>')


    def switch(self, cmd, channel, bool):

        address = self.config.get('address', channel)
        return self.sendOneCommand("sw o%s %s imme" % (address.zfill(2), bool), doClose=False, cmd=cmd)

    def getStatus(self, cmd, channel):

        address = self.config.get('address', channel)
        ret = self.sendOneCommand("read status o%s format" % address.zfill(2), doClose=False, cmd=cmd)

        if "pending" in ret:
            time.sleep(1)
            return self.getStatus(cmd, channel)
        else:
            return "on" if ' on' in ret.split('\r\n')[1] else "off"

    def formatException(self, e, traceback=""):

        return "%s %s %s" % (str(type(e)).replace("'", ""), str(type(e)(*e.args)).replace("'", ""), traceback)

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
                s.connect((self.tcpHost, self.tcpPort))
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

    def closeSock(self):
        """ close socket

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """

        if self.sock is not None:
            try:
                self.sock.close()

            except Exception as e:
                raise Exception("%s failed to close socket : %s" % (self.name, self.formatException(e)))

        self.sock = None

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """ Send one command and return one response.

        Args
        ----
        cmdStr : str
           The command to send.
        doClose : bool
           If True (the default), the device socket is closed before returning.

        Returns
        -------
        str : the single response string, with EOLs stripped.

        Raises
        ------
        IOError : from any communication errors.
        """

        if cmd is None:
            cmd = self.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)

        s = self.connectSock()

        try:
            s.sendall(fullCmd)

        except Exception as e:
            raise Exception("%s failed to send %s : %s" % (self.name.upper(), fullCmd, self.formatException(e)))

        reply = self.getOneResponse(sock=s, cmd=cmd)
        if doClose:
            self.closeSock()

        return reply

    def getOneResponse(self, sock=None, cmd=None):
        if sock is None:
            sock = self.connectSock()

        ret = self.ioBuffer.getOneResponse(sock=sock, cmd=cmd)
        reply = ret.strip()

        self.logger.debug('received %r', reply)

        return reply




def main():
    actor = DcbActor('dcb', productName='dcbActor')
    actor.run()


if __name__ == '__main__':
    main()
