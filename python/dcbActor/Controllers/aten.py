__author__ = 'alefur'
import logging

from enuActor.Controllers import pdu as pdu
from enuActor.Simulators.pdu import PduSim


class aten(pdu.pdu):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        pdu.pdu.__init__(self, actor, name, loglevel=loglevel)
        self.sim = PduSim()
        self.state = {}

    def _testComm(self, cmd):
        """| test communication
        | Called by FSMDev.loadDevice()

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        cmd.inform('atenVAW=%s,%s,%s' % self.measureVaw(cmd))

    def getStatus(self, cmd):
        """| get all port status

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        for outlet in self.powerNames.keys():
            self.portStatus(cmd, outlet=outlet)

        cmd.inform('atenVAW=%s,%s,%s' % self.measureVaw(cmd))

    def portStatus(self, cmd, outlet):
        """| get state outlet

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        state = self.sendOneCommand('read status o%s simple' % outlet, cmd=cmd)
        self.setState(cmd, self.powerNames[outlet], state)

    def setState(self, cmd, channel, state):
        """| set channel state

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        self.state[channel] = state
        cmd.inform('%s=%s' % (channel, state))

    def measureVaw(self, cmd):
        """| check total voltage, current and power

        :param cmd: on going command,
        :raise: Exception if the communication has failed with the controller
        """
        voltage = self.sendOneCommand('read meter dev volt simple', cmd=cmd)
        current = self.sendOneCommand('read meter dev curr simple', cmd=cmd)
        power = self.sendOneCommand('read meter dev pow simple', cmd=cmd)

        return voltage, current, power

    def authenticate(self, pwd=None):
        """| log to the telnet server

        :param cmd : current command,
        """
        pdu.pdu.authenticate(self, pwd='pfsait')
