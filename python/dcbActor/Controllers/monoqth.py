import logging
import time

import enuActor.utils.bufferedSocket as bufferedSocket
from dcbActor.Controllers.simulator.monoqth import Monoqthsim
from enuActor.utils.fsmThread import FSMThread


def getBit(word, ind):
    return not (not (2 ** ind) & word)


class monoqth(FSMThread, bufferedSocket.EthComm):
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
        substates = ['IDLE', 'TURNING_OFF', 'WARMING', 'FAILED']
        events = [{'name': 'turnoff', 'src': 'IDLE', 'dst': 'TURNING_OFF'},
                  {'name': 'turnon', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['TURNING_OFF', 'WARMING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['TURNING_OFF', 'WARMING'], 'dst': 'FAILED'},
                  ]
        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('TURNING_OFF', self.turnOff)
        self.addStateCB('WARMING', self.turnOn)
        self.sim = Monoqthsim()

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

    def _loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """
        self.mode = self.actor.config.get('monoqth', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('monoqth', 'host'),
                                        port=int(self.actor.config.get('monoqth', 'port')),
                                        EOL='\r\n')

    def _openComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r', timeout=5.0)
        self.connectSock()

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock()

    def _testComm(self, cmd):
        cmd.inform('monoqthVAW=%s,%s,%s' % self.checkVaw(cmd))

    def getStatus(self, cmd):

        stb = self.getStb(cmd=cmd)
        state = 'on' if getBit(stb, 7) else 'off'
        cmd.inform('monoqth=%s,%d,%d' % (state, stb, self.getEsr(cmd=cmd)))
        cmd.inform('monoqthVAW=%s,%s,%s' % self.checkVaw(cmd))

    def turnOn(self, cmd):
        self.turnQth(cmd=cmd, bool=True)

    def turnOff(self, cmd):
        self.turnQth(cmd=cmd, bool=False)

    def turnQth(self, cmd, bool):
        cmdStr = 'START' if bool else 'STOP'
        self.sendOneCommand(cmdStr, cmd=cmd)

        cond = not bool
        while cond != bool:
            time.sleep(2)
            try:
                cond = self.getState(cmd)
                cmd.inform('monoqthVAW=%s,%s,%s' % self.checkVaw(cmd))
            except Exception as e:
                cmd.warn('text=%s' % self.actor.strTraceback(e))

    def getStb(self, cmd):
        stb = self.sendOneCommand('STB?', cmd=cmd)

        return int(stb.split('STB')[1], 16)

    def getEsr(self, cmd):
        esr = self.sendOneCommand('ESR?', cmd=cmd)

        return int(esr.split('ESR')[1], 16)

    def getState(self, cmd):
        stb = self.getStb(cmd=cmd)
        return getBit(stb, 7)

    def checkVaw(self, cmd):

        voltage = self.sendOneCommand('VOLTS?', cmd=cmd)
        current = self.sendOneCommand('AMPS?', cmd=cmd)
        power = self.sendOneCommand('WATTS?', cmd=cmd)

        return voltage, current, power

    def getError(self, cmd):
        stb = self.getStb(cmd=cmd)
        esr = self.getEsr(cmd=cmd)

        for ind, val in self.STB.items():
            cmd.inform('%s=%s' % (val, ('1' if getBit(stb, ind) else '0')))

        for ind, val in self.ESR.items():
            cmd.inform('%s=%s' % (val, ('1' if getBit(esr, ind) else '0')))

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        if not self.actor.controllers['aten'].pow_mono == 'on':
            raise UserWarning('monochromator is not powered on')

        return bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
