#!/usr/bin/env python

import argparse
import configparser
import logging

import actorcore.ICC
import dcbActor.utils.makeLamDesign as lamConfig
import numpy as np
from twisted.internet import reactor


class OurActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile)
        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.onWarmup = False
        self.onsubstate = 'IDLE'

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

    @property
    def state(self):
        states = ['OFF', 'LOADED', 'ONLINE']
        state2logic = dict([(state, val) for val, state in enumerate(states)])
        logic2state = dict([(val, state) for val, state in enumerate(states)])
        if self.controllers.values():
            minLogic = np.min([state2logic[ctrl.states.current] for ctrl in self.controllers.values()])
            state = logic2state[minLogic]
        else:
            state = 'OFF'

        return state

    @property
    def substate(self):

        substates = [controller.substates.current for controller in self.controllers.values()]
        isNotIdle = [substate != 'IDLE' for substate in substates]

        if sum(isNotIdle) == 0:
            substate = 'IDLE'
        elif sum(isNotIdle) == 1:
            substate = substates[int(np.argmax(isNotIdle))]
        else:
            substate = 'BUSY'

        return substate

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching Controllers")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True
            logging.info("All Controllers started")

    def statusLoop(self, controller):
        try:
            self.callCommand("%s status" % (controller))
        except:
            pass

        if self.monitors[controller] > 0:
            reactor.callLater(self.monitors[controller],
                              self.statusLoopCB,
                              controller)

    def monitor(self, controller, period, cmd=None):
        cmd = cmd if cmd is not None else self.bcast

        if controller not in self.monitors:
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:

            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller], controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))

    def updateStates(self, cmd, onsubstate=False):
        cmd.inform('metaFSM=%s,%s' % (self.state, self.substate))

    def pfsDesignId(self, cmd):
        conf = configparser.ConfigParser()
        conf.read_file(open('/software/ait/fiberConfig.cfg'))
        fibers = [fib.strip() for fib in conf.get('current', 'fibers').split(',')]
        pfiDesignId = lamConfig.hashColors(fibers)

        cmd.inform('fiberConfig=%s' % ';'.join(fibers))
        cmd.inform('designId=0x%016x' % pfiDesignId)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='dcb', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = OurActor('dcb',
                        productName='dcbActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
