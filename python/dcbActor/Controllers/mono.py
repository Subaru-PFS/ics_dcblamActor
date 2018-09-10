__author__ = 'alefur'
import logging

import enuActor.Controllers.bufferedSocket as bufferedSocket
from actorcore.FSM import FSMDev
from actorcore.QThread import QThread
from dcbActor.Controllers.simulator.monosim import Monosim


class mono(FSMDev, QThread, bufferedSocket.EthComm):
    shutterCode = {'O': 'open', 'C':'closed'}
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

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\r\n')
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
        FSMDev.start(self, cmd=cmd, doInit=doInit, mode=mode)
        QThread.start(self)

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

        ret = self.sendOneCommand('status', doClose=False, cmd=cmd)

    def init(self, cmd):
        mode = self.sendOneCommand('init', doClose=False, cmd=cmd)
        if mode != '1':
            raise ValueError('Monochromator is not in Handshake mode')

    def getStatus(self, cmd):
        cmd.inform('monoFSM=%s,%s' % (self.states.current, self.substates.current))
        cmd.inform('monoMode=%s' % self.mode)

        if self.states.current == 'ONLINE':
            shutter = self.getShutter(cmd=cmd)
            gratingId, linesPerMm, gratingLabel = self.getGrating(cmd=cmd)
            outport = int(self.getOutport(cmd=cmd))
            wavelength = float(self.getWavelength(cmd=cmd, doClose=True))
            cmd.inform('monograting=%d,%.3f,%s' % (int(gratingId), float(linesPerMm), gratingLabel))
            cmd.inform('monochromator=%s,%d,%.3f'%(shutter, outport, wavelength))

        cmd.finish()

    def getShutter(self, cmd, doClose=False):
        shutter = self.sendOneCommand('getshutter', doClose=doClose, cmd=cmd)
        return self.shutterCode[shutter]

    def getGrating(self, cmd, doClose=False):
        return self.sendOneCommand('getgrating', doClose=doClose, cmd=cmd).split(',')

    def getOutport(self, cmd, doClose=False):
        return self.sendOneCommand('getoutport', doClose=doClose, cmd=cmd)

    def getWavelength(self, cmd, doClose=False):
        return self.sendOneCommand('getwave', doClose=doClose, cmd=cmd)

    def setShutter(self, cmd, openShutter, doClose=False):
        func = 'open' if openShutter else 'close'
        mode = self.sendOneCommand('shutter%s'%func, doClose=doClose, cmd=cmd)

    def setGrating(self, cmd, gratingId, doClose=False):
        mode = self.sendOneCommand('getgrating,%d'%gratingId, doClose=doClose, cmd=cmd)

    def setOutport(self, cmd, outportId, doClose=False):
        mode = self.sendOneCommand('getoutport,%d'%outportId, doClose=doClose, cmd=cmd)

    def setWavelength(self, cmd, wavelength, doClose=False):
        mode = self.sendOneCommand('setwave,%.3f'%wavelength, doClose=doClose, cmd=cmd)

    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
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
