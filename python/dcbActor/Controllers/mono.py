__author__ = 'alefur'
import logging

import enuActor.utils.bufferedSocket as bufferedSocket
from dcbActor.Controllers.simulator.mono import Monosim
from enuActor.utils.fsmThread import FSMThread
from opscore.utility.qstr import qstr


class mono(FSMThread, bufferedSocket.EthComm):
    shutterCode = {'O': 'open', 'C': 'closed'}

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        substates = ['IDLE', 'MOVING', 'OPENING', 'CLOSING', 'FAILED']
        events = [{'name': 'setgrating', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'openshutter', 'src': 'IDLE', 'dst': 'OPENING'},
                  {'name': 'closeshutter', 'src': 'IDLE', 'dst': 'CLOSING'},
                  {'name': 'idle', 'src': ['MOVING', 'OPENING', 'CLOSING'], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', 'OPENING', 'CLOSING'], 'dst': 'FAILED'},
                  ]
        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('MOVING', self.setGrating)
        self.addStateCB('OPENING', self.openShutter)
        self.addStateCB('CLOSING', self.closeShutter)
        self.sim = Monosim()

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
        self.mode = self.actor.config.get('mono', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('mono', 'host'),
                                        port=int(self.actor.config.get('mono', 'port')),
                                        EOL='\r\n')

    def _openComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n', timeout=30.0)
        self.connectSock()

    def _closeComm(self, cmd):
        """| Close communication.
        | Called by FSMThread.stop()

        :param cmd: on going command
        """
        self.closeSock()

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        """
        wavelength = float(self.getWave(cmd=cmd))

    def getStatus(self, cmd):
        error = self.getError(cmd=cmd)
        shutter = self.getShutter(cmd=cmd)
        grating = self.getGrating(cmd=cmd)
        outport = int(self.getOutport(cmd=cmd))
        wavelength = float(self.getWave(cmd=cmd))

        gen = cmd.inform if error == 'OK' else cmd.warn
        gen('monoerror=%s' % qstr(error))
        gen('monograting=%s' % grating)
        gen('monochromator=%s,%d,%.3f' % (shutter, outport, wavelength))

    def openShutter(self, cmd):
        self.sendOneCommand('shutteropen', cmd=cmd)

    def closeShutter(self, cmd):
        self.sendOneCommand('shutterclose', cmd=cmd)

    def setGrating(self, cmd, gratingId):
        self.sendOneCommand('setgrating,%d' % gratingId, cmd=cmd)

    def getError(self, cmd):
        return self.sendOneCommand('geterror', cmd=cmd)

    def getShutter(self, cmd):
        shutter = self.sendOneCommand('getshutter', cmd=cmd)
        return self.shutterCode[shutter]

    def getGrating(self, cmd):
        return self.sendOneCommand('getgrating', cmd=cmd)

    def getOutport(self, cmd):
        return self.sendOneCommand('getoutport', cmd=cmd)

    def getWave(self, cmd):
        return self.sendOneCommand('getwave', cmd=cmd)

    def setOutport(self, cmd, outportId):
        self.sendOneCommand('setoutport,%d' % outportId, cmd=cmd)

    def setWave(self, cmd, wavelength):
        self.sendOneCommand('setwave,%.3f' % wavelength, cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=False, cmd=None):
        if not self.actor.controllers['aten'].pow_mono == 'on':
            raise UserWarning('monochromator is not powered on')

        reply = bufferedSocket.EthComm.sendOneCommand(self, cmdStr=cmdStr, doClose=doClose, cmd=cmd)
        error, ret = reply.split(',', 1)

        if int(error):
            raise UserWarning(ret)

        return ret

    def createSock(self):
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
