#!/usr/bin/env python


import ConfigParser
import argparse
import logging
import time
from datetime import datetime as dt

import actorcore.ICC
import numpy as np
from opscore.utility.qstr import qstr
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

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

        self.monitor(controller="labsphere", period=5)
        self.monitor(controller="aten", period=60)

    @property
    def arcState(self):
        return {"ne": self.controllers["aten"].state["ne"],
                "hgar": self.controllers["aten"].state["hgar"],
                "xenon": self.controllers["aten"].state["xenon"],
                "krypton": self.controllers["aten"].state["krypton"],
                "halogen": self.controllers["labsphere"].halogenBool}

    @property
    def flux(self):
        return np.array([val for date, val in self.controllers["labsphere"].arrPhotodiode])

    @property
    def warmingUp(self):
        if len(self.flux) > 10:
            return True
        else:
            return False

    def reloadConfiguration(self, cmd):
        logging.info("reading config file %s", self.configFile)

        try:
            newConfig = ConfigParser.ConfigParser()
            newConfig.read(self.configFile)
        except Exception, e:
            if cmd:
                cmd.fail('text=%s' % (qstr("failed to read the configuration file, old config untouched: %s" % (e))))
            raise

        self.config = newConfig
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching Controllers")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True
            logging.info("All Controllers started")

    def attachController(self, controller, instanceName=None, cmd=None):
        cmd = cmd if cmd is not None else self.bcast
        actorcore.ICC.ICC.attachController(self, controller, instanceName)

    def statusLoop(self, controller):
        if self.monitors[controller] > 0:
            try:
                self.callCommand("%s status" % (controller))
            except:
                pass

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
            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller],
                                                          controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))

    def switchArc(self, cmd, arcLamp, switchOn, attenVal, force):
        empty = False

        if attenVal is not None and self.controllers["labsphere"].attenVal != attenVal:
            self.controllers["labsphere"].switchAttenuator(cmd, attenVal)
            cmd.inform("text='attenuator adjusted'")

        nextArcState = self.arcState
        nextArcState[arcLamp] = switchOn

        if nextArcState != self.arcState:
            if arcLamp in ['ne', 'hgar', 'xenon', 'krypton']:
                ret = self.controllers["aten"].switch(cmd, arcLamp, switchOn)
                self.controllers["aten"].getStatus(cmd, [arcLamp], doClose=True)
            else:
                self.controllers["labsphere"].switchHalogen(cmd, switchOn)
            empty = True

        if empty:
            self.controllers["labsphere"].arrPhotodiode = []

        if switchOn:
            self.waitForFlux(cmd, force)

        cmd.finish("text='%s ok'" % arcLamp)

    def waitForFlux(self, cmd, force):
        t0 = dt.now()
        self.monitor(controller="labsphere", period=0, cmd=cmd)

        while not self.warmingUp:
            self.controllers["labsphere"].getStatus(cmd)
            time.sleep(5)
            cmd.inform("text='Warming up lamp'")

        if not force:
            while not (np.mean(self.flux) > 0.001 and np.std(self.flux) < 0.05):
                self.controllers["labsphere"].getStatus(cmd)
                time.sleep(5)
                cmd.inform("text='Waiting photodiode flux to stabilise meanFlux=%.2f stdFlux=%.2f'" % (np.mean(self.flux), np.std(self.flux)))
                if (dt.now() - t0).total_seconds() > 240:
                    raise Exception('Timeout photodiode flux is null or unstable')

        self.monitor(controller="labsphere", period=5, cmd=cmd)

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
