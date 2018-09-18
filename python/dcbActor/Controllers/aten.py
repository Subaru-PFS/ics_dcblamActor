__author__ = 'alefur'
import logging
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.atensim import Atensim


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

    @property
    def pow_labsphere(self):
        logsum = sum([1 if self.state[key] else 0 for key in ['pow_attenuator', 'pow_sphere', 'pow_halogen']])
        if logsum == 3:
            return 'on'
        elif logsum == 0:
            return 'off'
        else:
            return 'undef'

    @property
    def pow_mono(self):
        return self.state['pow_mono']

    def start(self, cmd=None, doInit=True, mode=None):
        QThread.start(self)
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)

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

        self.host = self.actor.config.get('aten', 'host')
        self.port = int(self.actor.config.get('aten', 'port'))
        self.mode = self.actor.config.get('aten', 'mode') if mode is None else mode

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('atenMode=%s' % self.mode)
        self.sim = Atensim()
        s = self.connectSock()

    def switch(self, cmd, channel, bool):
        bool = 'on' if bool else 'off'
        address = self.actor.config.get('address', channel)

        ret = self.sendOneCommand("sw o%s %s imme" % (address.zfill(2), bool), doClose=False, cmd=cmd)
        self.checkChannel(cmd=cmd,
                          channel=channel)

    def checkChannel(self, cmd, channel):

        address = self.actor.config.get('address', channel)

        ret = self.sendOneCommand('read status o%s format' % address.zfill(2), doClose=False, cmd=cmd)

        if 'pending' in ret:
            time.sleep(1)
            return self.checkChannel(cmd, channel)
        else:
            state = 'on' if ' on' in ret.split('\r\n')[1] else 'off'
            self.state[channel] = True if state == 'on' else False
            cmd.inform('%s=%s' % (channel, state))

    def getStatus(self, cmd):
        cmd.inform('atenFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('atenMode=%s' % self.mode)

        channels = [channel for channel in self.actor.config.options('address')]

        if self.states.current == 'ONLINE':

            for channel in channels:
                self.checkChannel(cmd=cmd, channel=channel)
            cmd.inform('pow_labsphere=%s' % self.pow_labsphere)

            v, a, w = self.checkVaw(cmd)
            cmd.inform('atenVAW=%s,%s,%s' % (v, a, w))

        self.closeSock()
        cmd.finish()

    def checkVaw(self, cmd):

        voltage = self.sendOneCommand('read meter dev volt simple', doClose=False, cmd=cmd)
        current = self.sendOneCommand('read meter dev curr simple', doClose=False, cmd=cmd)
        power = self.sendOneCommand('read meter dev pow simple', doClose=False, cmd=cmd)

        v = voltage.split('\r\n')[1].strip()
        a = current.split('\r\n')[1].strip()
        w = power.split('\r\n')[1].strip()

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

            self.sock = self.authenticate(sock=s)

        return self.sock

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def authenticate(self, sock):
        time.sleep(0.1)

        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Login: ' not in ret:
            raise ValueError('Could not login')

        sock.sendall('teladmin\r\n'.encode('utf-8'))

        time.sleep(0.1)
        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Password:' not in ret:
            raise ValueError('Bad login')

        sock.sendall('pfsait\r\n'.encode('utf-8'))

        time.sleep(0.1)
        ret = sock.recv(1024).decode('utf-8', 'ignore')

        if 'Logged in successfully' not in ret:
            raise ValueError('Bad password')

        return sock

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
