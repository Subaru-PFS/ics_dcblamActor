#!/usr/bin/env python


import ConfigParser
import argparse
import logging
import time
from datetime import datetime as dt
import numpy as np
import actorcore.ICC
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
        try:
            self.callCommand("%s status" % (controller))
        except:
            pass

        if self.monitors[controller] > 0:
            reactor.callLater(self.monitors[controller],
                              self.statusLoopCB,
                              controller)

    def monitor(self, controller, period, cmd=None):
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

    def switchArc(self, cmd, arcLamp, attenVal):
        t0 = dt.now()

        cond = False
        self.controllers["labsphere"].switchAttenuator(cmd, attenVal)

        if arcLamp in ['ne', 'hgar', 'xenon']:
            ret = self.controllers["aten"].switch(cmd, arcLamp, "on")
            self.controllers["aten"].getStatus(cmd, [arcLamp], doClose=True)
        else:
            self.controllers["labsphere"].switchHalogen(cmd, True)

        #thFlux = {'ne': 4.0, 'hgar': 2.0, 'halogen': 5.5}

        self.controllers["labsphere"].arrPhotodiode = []
        while not cond:
            self.controllers["labsphere"].getStatus(cmd)
            arrPhotodiode = [val for date, val in self.controllers["labsphere"].arrPhotodiode]

            if len(arrPhotodiode) > 10 and np.std(arrPhotodiode) < 0.05:
                cond = True
            else:
                time.sleep(5)

            if (dt.now() - t0).total_seconds() > 240:
                raise Exception("Timeout switching Arc")


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
