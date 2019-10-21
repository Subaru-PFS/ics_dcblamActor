#!/usr/bin/env python


from enuActor.Commands import PduCmd as PduCmd


class AtenCmd(PduCmd.PduCmd):
    def __init__(self, actor):
        PduCmd.PduCmd.__init__(self, actor, 'aten')
