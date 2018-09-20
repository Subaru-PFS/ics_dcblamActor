import socket
import time


class Monoqthsim(socket.socket):
    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
        self.lampOn = False

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
            word = '21' if not self.lampOn else 'A1'
            self.buf.append('STB%s\r' % word)

        elif cmdStr == 'ESR?\r\n':
            self.buf.append('ESR01\r')

        elif cmdStr == 'AMPS?\r\n':
            self.buf.append('2.0\r')

        elif cmdStr == 'VOLTS?\r\n':
            self.buf.append('230.0\r')

        elif cmdStr == 'WATTS?\r\n':
            self.buf.append('460.0\r')

        elif cmdStr == 'STOP\r\n':
            self.lampOn = False
            self.buf.append('\r')

        elif cmdStr == 'START\r\n':
            self.lampOn = True
            self.buf.append('\r')
        else:
            raise ValueError('unknown command')

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
