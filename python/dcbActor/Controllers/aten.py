__author__ = 'alefur'
import logging
import time

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.aten import Atensim


class aten(FSMDev, QThread, bufferedSocket.EthComm):
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

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('SWITCHING', self.switch)

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
        logsum = sum([1 if self.state[key] == 'on' else 0 for key in ['pow_attenuator', 'pow_sphere', 'pow_halogen']])
        if logsum == 3:
            return 'on'
        elif logsum == 0:
            return 'off'
        else:
            return 'undef'

    @property
    def pow_mono(self):
        return self.state['pow_mono']

    def getChannel(self, outlet):
        return {'Outlet %s' % (v.strip()).zfill(2): k for k, v in self.actor.config.items('outlets')}[outlet]

    def getOutlet(self, channel):
        return self.actor.config.get('outlets', channel).strip().zfill(2)

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

    def switch(self, e):
        toSwitch = dict([(channel, 'on') for channel in e.switchOn] + [(channel, 'off') for channel in e.switchOff])

        labsphere = toSwitch.pop('labsphere', None)
        if labsphere is not None:
            toSwitch['pow_attenuator'] = labsphere
            toSwitch['pow_sphere'] = labsphere
            toSwitch['pow_halogen'] = labsphere

        try:
            for channel, state in toSwitch.items():
                cmdStr = "sw o%s %s imme" % (self.getOutlet(channel=channel), state)
                ret = self.sendOneCommand(cmdStr=cmdStr, cmd=e.cmd)
                self.checkChannel(cmd=e.cmd, channel=channel)
                time.sleep(2)

            self.substates.idle(cmd=e.cmd)

        except:
            self.substates.fail(cmd=e.cmd)
            raise

    def checkChannel(self, cmd, channel):

        outlet = self.getOutlet(channel=channel)

        ret = self.sendOneCommand('read status o%s format' % outlet, cmd=cmd)
        outlet, state = ret.rsplit(' ', 1)

        self.setState(cmd=cmd, channel=self.getChannel(outlet=outlet), state=state)

    def getStatus(self, cmd):
        cmd.inform('atenMode=%s' % self.mode)
        cmd.inform('atenFSM=%s,%s' % (self.states.current, self.substates.current))

        channels = [channel for channel in self.actor.config.options('outlets')]

        if self.states.current == 'ONLINE':

            try:
                for channel in channels:
                    self.checkChannel(cmd=cmd, channel=channel)

                cmd.inform('pow_labsphere=%s' % self.pow_labsphere)
                cmd.finish('atenVAW=%s,%s,%s' % self.checkVaw(cmd))

            except:
                raise

            finally:
                self.closeSock()

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

            self.sock = self.authenticate(sock=s)

        return self.sock

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        fullCmd = '%s%s' % (cmdStr, self.EOL)
        reply = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)
        if fullCmd not in reply:
            raise ValueError('Command was not echoed properly')

        return reply.split(fullCmd)[1].strip()

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
