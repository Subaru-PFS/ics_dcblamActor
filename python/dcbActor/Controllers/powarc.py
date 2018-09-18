import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.powarcsim import Powarcsim


def getBit(word, ind):
    return not (not (2 ** ind) & word)


class powarc(FSMDev, QThread, bufferedSocket.EthComm):
    STB = {7: 'lamp_on',
           6: 'ext',
           5: 'power_mode',
           4: 'cal_mode',
           3: 'fault',
           2: 'comm',
           1: 'limit',
           0: 'interlock',
           }

    ESR = {7: 'power_on',
           6: 'user_request',
           5: 'command_error',
           4: 'execution_error',
           3: 'device_dependent_error',
           2: 'query_error',
           1: 'request_control',
           0: 'operation_complete',
           }

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

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r', timeout=5.0)
        self.EOL = '\r\n'
        self.sock = None

        self.mode = ''
        self.sim = None

    @property
    def simulated(self):
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

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

        self.host = self.actor.config.get('powarc', 'host')
        self.port = int(self.actor.config.get('powarc', 'port'))
        self.mode = self.actor.config.get('powarc', 'mode') if mode is None else mode

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('powarcMode=%s' % self.mode)
        self.sim = Powarcsim()
        s = self.connectSock()

        cmd.inform('powarcVAW=%s,%s,%s' % self.checkVaw(cmd))


    def switch(self, cmd, bool):
        cmdStr = 'START' if bool else 'STOP'
        self.sendOneCommand(cmdStr, doClose=False, cmd=cmd)

    def getStb(self, cmd):
        stb = self.sendOneCommand('STB?', doClose=False, cmd=cmd)

        return int(stb.split('STB')[1], 16)

    def getEsr(self, cmd, doClose=False):
        esr = self.sendOneCommand('ESR?', doClose=doClose, cmd=cmd)

        return int(esr.split('ESR')[1], 16)

    def checkVaw(self, cmd):

        voltage = self.sendOneCommand('VOLTS?', doClose=False, cmd=cmd)
        current = self.sendOneCommand('AMPS?', doClose=False, cmd=cmd)
        power = self.sendOneCommand('WATTS?', doClose=True, cmd=cmd)

        return voltage, current, power

    def getStatus(self, cmd):
        cmd.inform('powarcFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('powarcMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            stb = self.getStb(cmd=cmd)
            state = 'on' if getBit(stb, 7) else 'off'
            cmd.inform('powarc=%s,%d,%d' % (state, stb, self.getEsr(cmd=cmd)))
            cmd.inform('powarcVAW=%s,%s,%s' % self.checkVaw(cmd))

        cmd.finish()

    def getError(self, cmd):
        stb = self.getStb(cmd=cmd)
        esr = self.getEsr(cmd=cmd, doClose=True)

        for ind, val in self.STB.items():
            cmd.inform('%s=%s' % (val, ('1' if getBit(stb, ind) else '0')))

        for ind, val in self.ESR.items():
            cmd.inform('%s=%s' % (val, ('1' if getBit(esr, ind) else '0')))

        cmd.finish()

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s

    def sendOneCommand(self, *args, **kwargs):
        if not self.actor.controllers['aten'].pow_mono:
            raise UserWarning('monochromator is not powered on')

        return bufferedSocket.EthComm.sendOneCommand(self, *args, **kwargs)

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
