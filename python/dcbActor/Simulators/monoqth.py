import random
import socket
import time
from threading import Thread


class Monoqthsim(socket.socket):
    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
        self.qthOn = False
        self.power = 0

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

        if cmdStr == 'STB?\r\n':
            word = '21' if not self.qthOn else 'A1'
            self.buf.append('STB%s\r' % word)

        elif cmdStr == 'ESR?\r\n':
            self.buf.append('ESR01\r')

        elif cmdStr == 'AMPS?\r\n':
            self.buf.append('2.0\r')

        elif cmdStr == 'VOLTS?\r\n':
            self.buf.append('230.0\r')

        elif cmdStr == 'WATTS?\r\n':
            power = self.power + random.gauss(mu=0, sigma=0.02)
            self.buf.append('%.1f\r' % power)

        elif cmdStr == 'STOP\r\n':
            f1 = Thread(target=self.turnQth, args=(False,))
            f1.start()
            self.buf.append('\r')

        elif cmdStr == 'START\r\n':
            f1 = Thread(target=self.turnQth, args=(True,))
            f1.start()
            self.buf.append('\r')
        else:
            raise ValueError('unknown command')

    def turnQth(self, bool, duration=10, tempo=0.05):
        powFin = 40 if bool else 0
        coeff = (powFin - self.power) / duration

        while abs(self.power - powFin) > 0.05:
            self.power += round(coeff * tempo, 3)
            time.sleep(tempo)

        self.qthOn = bool

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
