#!/usr/bin/env python

import argparse
import configparser
import logging

import actorcore.ICC
import dcbActor.utils.makeLamDesign as lamConfig
import numpy as np


class DcbActor(actorcore.ICC.ICC):
    stateList = ['OFF', 'LOADED', 'ONLINE']
    state2logic = dict([(state, val) for val, state in enumerate(stateList)])
    logic2state = {v: k for k, v in state2logic.items()}

    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile)
        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.onsubstate = 'IDLE'

    @property
    def arcs(self):
        return {"neon": self.controllers['aten'].state["neon"],
                "hgar": self.controllers['aten'].state["hgar"],
                "xenon": self.controllers['aten'].state["xenon"],
                "krypton": self.controllers['aten'].state["krypton"],
                "argon": self.controllers['aten'].state["argon"],
                "deuterium": self.controllers['aten'].state["deuterium"],
                "halogen": self.controllers['labsphere'].halogen}

    @property
    def states(self):
        return [controller.states.current for controller in self.controllers.values()]

    @property
    def substates(self):
        return [controller.substates.current for controller in self.controllers.values()]

    @property
    def state(self):
        if not self.controllers.values():
            return 'OFF'

        minLogic = np.min([DcbActor.state2logic[state] for state in self.states])
        return DcbActor.logic2state[minLogic]

    @property
    def substate(self):
        if not self.controllers.values():
            return 'IDLE'

        if 'FAILED' in self.substates:
            substate = 'FAILED'
        elif list(set(self.substates)) == ['IDLE']:
            substate = 'IDLE'
        else:
            substate = self.onsubstate

        return substate

    @property
    def monitors(self):
        return dict([(name, controller.monitor) for name, controller in self.controllers.items()])

    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True

    def monitor(self, controller, period, cmd=None):
        cmd = self.bcast if cmd is None else cmd

        if controller not in self.controllers:
            raise ValueError('controller %s is not connected' % controller)

        self.controllers[controller].monitor = period
        cmd.warn('text="setting %s loop to %gs"' % (controller, period))

    def updateStates(self, cmd, onsubstate=False):
        self.onsubstate = onsubstate if onsubstate and onsubstate != 'IDLE' else self.onsubstate

        cmd.inform('metaFSM=%s,%s' % (self.state, self.substate))

    def pfsDesignId(self, cmd):
        conf = configparser.ConfigParser()
        conf.read_file(open('/software/ait/fiberConfig.cfg'))
        fibers = [fib.strip() for fib in conf.get('current', 'fibers').split(',')]
        pfiDesignId = lamConfig.hashColors(fibers)

        cmd.inform('fiberConfig="%s"' % ';'.join(fibers))
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

    theActor = DcbActor('dcb',
                        productName='dcbActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
