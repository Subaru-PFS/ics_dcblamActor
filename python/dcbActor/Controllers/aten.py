__author__ = 'alefur'
import logging
import time

import enuActor.utils.bufferedSocket as bufferedSocket
from dcbActor.Controllers.simulator.aten import Atensim
from enuActor.utils.fsmThread import FSMThread


class aten(FSMThread, bufferedSocket.EthComm):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        substates = ['IDLE', 'SWITCHING', 'FAILED']
        events = [{'name': 'switch', 'src': 'IDLE', 'dst': 'SWITCHING'},
                  {'name': 'idle', 'src': ['SWITCHING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['SWITCHING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('SWITCHING', self.switch)
        self.state = {}

        self.mode = ''
        self.sock = None
        self.sim = None

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

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
        return self.state['pow_labsphere']

    @property
    def pow_mono(self):
        return self.state['pow_mono']

    def getChannel(self, outlet):
        return {'Outlet %s' % (v.strip()).zfill(2): k for k, v in self.actor.config.items('outlets')}[outlet]

    def getOutlet(self, channel):
        return self.actor.config.get('outlets', channel).strip().zfill(2)

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('aten', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('aten', 'host'),
                                        port=int(self.actor.config.get('aten', 'port')),
                                        EOL='\r\n')

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.sim = Atensim()

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n>')
        self.connectSock()

    def init(self, cmd):
        cmd.inform('atenVAW=%s,%s,%s' % self.checkVaw(cmd))

    def getStatus(self, cmd):
        for channel in [channel for channel in self.actor.config.options('outlets')]:
            self.checkChannel(cmd=cmd, channel=channel)

        cmd.inform('atenVAW=%s,%s,%s' % self.checkVaw(cmd))

    def switch(self, e):
        toSwitch = dict([(channel, 'on') for channel in e.switchOn] + [(channel, 'off') for channel in e.switchOff])

        try:
            for channel, state in toSwitch.items():
                cmdStr = "sw o%s %s imme" % (self.getOutlet(channel=channel), state)
                ret = self.sendOneCommand(cmdStr=cmdStr, cmd=e.cmd, doRaise=False)
                self.checkChannel(cmd=e.cmd, channel=channel)
                time.sleep(2)

            self.substates.idle(cmd=e.cmd)

        except:
            self.substates.fail(cmd=e.cmd)
            raise

        finally:
            self.closeSock()

    def checkChannel(self, cmd, channel):

        outlet = self.getOutlet(channel=channel)

        ret = self.sendOneCommand('read status o%s format' % outlet, cmd=cmd)
        outlet, state = ret.rsplit(' ', 1)

        self.setState(cmd=cmd, channel=self.getChannel(outlet=outlet), state=state)

    def checkVaw(self, cmd):

        voltage = self.sendOneCommand('read meter dev volt simple', cmd=cmd)
        current = self.sendOneCommand('read meter dev curr simple', cmd=cmd)
        power = self.sendOneCommand('read meter dev pow simple', cmd=cmd)

        return voltage, current, power

    def setState(self, cmd, channel, state):

        self.state[channel] = state
        cmd.inform('%s=%s' % (channel, state))

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

            try:
                self.sock = self.authenticate(sock=s)
            except ValueError:
                self.closeSock()
                return self.connectSock()

        return self.sock

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None, doRaise=True):
        fullCmd = '%s%s' % (cmdStr, self.EOL)
        reply = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

        return self.parseResponse(cmd=cmd, fullCmd=fullCmd, reply=reply, doRaise=doRaise)

    def parseResponse(self, cmd, fullCmd, reply, doRaise, retry=True):
        if fullCmd in reply:
            return reply.split(fullCmd)[1].strip()

        if retry:
            time.sleep(1)
            reply = self.getOneResponse(cmd=cmd)
            return self.parseResponse(cmd=cmd, fullCmd=fullCmd, reply=reply, doRaise=doRaise, retry=False)

        if doRaise:
            raise ValueError('Command was not echoed properly')

        return

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
