__author__ = 'alefur'
import logging
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket

from dcbActor.Controllers.simulator.atensim import Atensim
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread


class aten(FSMDev, QThread, bufferedSocket.EthComm):
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

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n>')
        self.EOL = '\r\n'

        self.mode = ''
        self.sim = None

        self.state = {}

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    def start(self, cmd=None, doInit=True):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit)

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

        self.host = self.actor.config.get('aten', 'host')
        self.port = int(self.actor.config.get('aten', 'port'))
        self.mode = self.actor.config.get('aten', 'mode')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """

        self.sim = Atensim()
        s = self.connectSock()

    def switch(self, cmd, channel, bool):
        bool = 'on' if bool else 'off'
        address = self.actor.config.get('address', channel)

        return self.sendOneCommand("sw o%s %s imme" % (address.zfill(2), bool), doClose=False, cmd=cmd)


    def checkChannel(self, cmd, channel):

        address = self.actor.config.get('address', channel)

        ret = self.sendOneCommand('read status o%s format' % address.zfill(2), doClose=False, cmd=cmd)

        if 'pending' in ret:
            time.sleep(1)
            return self.checkChannel(cmd, channel)
        else:
            state = 'on' if ' on' in ret else 'off'
            self.state[channel] = state
            cmd.inform('%s=%s' % (channel, state))

    def getStatus(self, cmd):

        channels = [channel for channel in self.actor.config.options('address')]

        cmd.inform('atenMode=%s' % self.mode)
        # self.actor.getState(cmd)

        if self.states.current == 'ONLINE':

            for channel in channels:
                self.checkChannel(cmd=cmd, channel=channel)

            v, a, w = self.checkVaw(cmd)
            cmd.inform('aten_vaw=%s,%s,%s' % (v, a, w))

        self.closeSock()
        cmd.finish()


    def checkVaw(self, cmd):

        v = self.sendOneCommand('read meter dev volt simple', doClose=False, cmd=cmd)
        a = self.sendOneCommand('read meter dev curr simple', doClose=False, cmd=cmd)
        w = self.sendOneCommand('read meter dev pow simple', doClose=False, cmd=cmd)

        return v, a, w

    def connectSock(self):
        """ Connect socket if self.sock is None

        :param cmd : current command,
        :return: sock in operation
                 bsh simulator in simulation
        """
        if self.sock is None:
            s = self.createSock()
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock = s
            try:
                self.authenticate()
            except:
                self.closeSock()
                raise

        return self.sock

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def authenticate(self):

        ret = self.sock.recv(1024)
        ret = ret.decode()

        if 'Login: ' not in ret:
            raise ValueError('Could not login')

        ret = self.sendOneCommand('teladmin', doClose=False)
        if 'Password:' not in ret:
            raise ValueError('Bad login')

        ret = self.sendOneCommand('pfsait', doClose=False)

        if 'Logged in successfully' not in ret:
            raise ValueError('Bad password')


    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
