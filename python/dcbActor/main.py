#!/usr/bin/env python

from actorcore.Actor import Actor


class DcbActor(Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Actor.__init__(self, name,
                       productName=productName,
                       configFile=configFile)


    def compute(self, expTime):
        return 10*expTime

def main():
    actor = DcbActor('dcb', productName='dcbActor')
    actor.run()


if __name__ == '__main__':
    main()
