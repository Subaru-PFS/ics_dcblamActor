import time
import socket
import random


class Labspheresim(socket.socket):

    def __init__(self, actor):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
        self.actor = actor

    def connect(self, server):
        (ip, port) = server
        time.sleep(0.5)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def fakeSend(self, cmdStr):
        time.sleep(0.1)
        cmdStr = cmdStr.decode()

        if cmdStr == 'O0X':
            photodiode = (random.randint(-9, 9)) / 100000
            try:
                offset = 3.2 if True in self.actor.arcState.values() else 0
            except KeyError:
                offset = 0

            photodiode += offset
            self.buf.append('%g\r\n' % photodiode)
        else:
            self.buf.append('ok\r\n')

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
