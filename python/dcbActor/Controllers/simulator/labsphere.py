import random
import socket
import time


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
            offset = 3.2 if 'on' in self.actor.arcs.values() else 0
            ratio = (255-self.actor.controllers['labsphere'].attenuator)/255
            noise = random.gauss(mu=0.0005, sigma=0.005)
            self.buf.append('%g\r\n' % (ratio * offset + noise))
        else:
            self.buf.append('\r\n')

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
