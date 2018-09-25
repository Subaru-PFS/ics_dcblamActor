__author__ = 'alefur'
import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.mono import Monosim
from opscore.utility.qstr import qstr


class mono(FSMDev, QThread, bufferedSocket.EthComm):
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

        bufferedSocket.EthComm.__init__(self)
        QThread.__init__(self, actor, name)
        FSMDev.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.setGrating)
        self.addStateCB('OPENING', self.openShutter)
        self.addStateCB('CLOSING', self.closeShutter)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n', timeout=30.0)
        self.EOL = '\r\n'

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

        try:
            self.actor.attachController(name='monoqth')
        except Exception as e:
            cmd.warn('text="%s' % self.actor.strTraceback(e))

    def stop(self, cmd=None):
        FSMDev.stop(self, cmd=cmd)

        try:
            self.actor.detachController(controllerName='monoqth')
        except Exception as e:
            cmd.warn('text="%s' % self.actor.strTraceback(e))

        self.exit()

    def loadCfg(self, cmd, mode=None):
        """| Load Configuration file. called by device.loadDevice()

        :param cmd: on going command
        :param mode: operation|simulation, loaded from config file if None
        :type mode: str
        :raise: Exception Config file badly formatted
        """

        self.host = self.actor.config.get('mono', 'host')
        self.port = int(self.actor.config.get('mono', 'port'))
        self.mode = self.actor.config.get('mono', 'mode') if mode is None else mode

    def startComm(self, cmd):
        """| Start socket with the interlock board or simulate it.
        | Called by device.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('monoMode=%s' % self.mode)

        self.sim = Monosim()
        s = self.connectSock()

        status = self.sendOneCommand('status', doClose=True, cmd=cmd)
        cmd.inform('text=%s' % qstr(status))

    def getStatus(self, cmd):
        cmd.inform('monoMode=%s' % self.mode)
        cmd.inform('monoFSM=%s,%s' % (self.states.current, self.substates.current))

        if self.states.current == 'ONLINE':
            error = self.getError(cmd=cmd)
            shutter = self.getShutter(cmd=cmd)
            grating = self.getGrating(cmd=cmd)
            outport = int(self.getOutport(cmd=cmd))
            wavelength = float(self.getWave(cmd=cmd, doClose=True))
            talk = cmd.inform if error == 'OK' else cmd.warn
            talk('monoerror=%s' % qstr(error))

            cmd.inform('monograting=%s' % grating)
            cmd.inform('monochromator=%s,%d,%.3f' % (shutter, outport, wavelength))

        cmd.finish()

    def getError(self, cmd, doClose=False):
        return self.sendOneCommand('geterror', doClose=doClose, cmd=cmd)

    def getShutter(self, cmd, doClose=False):
        shutter = self.sendOneCommand('getshutter', doClose=doClose, cmd=cmd)
        return self.shutterCode[shutter]

    def getGrating(self, cmd, doClose=False):
        return self.sendOneCommand('getgrating', doClose=doClose, cmd=cmd)

    def getOutport(self, cmd, doClose=False):
        return self.sendOneCommand('getoutport', doClose=doClose, cmd=cmd)

    def getWave(self, cmd, doClose=False):
        return self.sendOneCommand('getwave', doClose=doClose, cmd=cmd)

    def openShutter(self, e):
        try:
            self.sendOneCommand('shutteropen', doClose=False, cmd=e.cmd)
            self.substates.idle(cmd=e.cmd)
        except:
            self.substates.fail(cmd=e.cmd)
            raise

    def closeShutter(self, e):
        try:
            self.sendOneCommand('shutterclose', doClose=False, cmd=e.cmd)
            self.substates.idle(cmd=e.cmd)
        except:
            self.substates.fail(cmd=e.cmd)
            raise

    def setGrating(self, e):
        try:
            self.sendOneCommand('setgrating,%d' % e.gratingId, doClose=False, cmd=e.cmd)
            self.substates.idle(cmd=e.cmd)
        except:
            self.substates.fail(cmd=e.cmd)
            raise

    def setOutport(self, cmd, outportId, doClose=False):
        self.sendOneCommand('setoutport,%d' % outportId, doClose=doClose, cmd=cmd)

    def setWave(self, cmd, wavelength, doClose=False):
        self.sendOneCommand('setwave,%.3f' % wavelength, doClose=doClose, cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
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

    def handleTimeout(self):
        if self.exitASAP:
            raise SystemExit()
