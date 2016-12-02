__author__ = 'alefur'
import logging

from actorcore.QThread import QThread


class Device(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        QThread.__init__(self, actor, name, timeout=2)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.sock = None

    def formatException(self, e, traceback=""):

        return "%s %s %s" % (str(type(e)).replace("'", ""), str(type(e)(*e.args)).replace("'", ""), traceback)

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

    def stop(self):
        self.exit()

    def handleTimeout(self):
        pass
