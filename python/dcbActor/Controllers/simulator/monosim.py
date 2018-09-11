import socket
import time


class Monosim(socket.socket):

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
        self.handshake = 0
        self.shutterOpen = False
        self.grating = 1
        self.outport = 1
        self.wavelength = 300

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
        cmdStr = cmdStr.split('\r\n')[0]
        funcname = cmdStr.split(',')[0]
        args = cmdStr.split(',')[1:]

        if funcname == 'status':
            self.buf.append('0,Oriel monochromator\r\n')

        elif funcname == 'init':
            self.handshake = 1
            self.buf.append('0,%d\r\n' % self.handshake)

        elif funcname == 'getshutter':
            shutter = 'O' if self.shutterOpen else 'C'
            self.buf.append('0,%s\r\n' % shutter)

        elif funcname == 'getgrating':
            self.buf.append('0,%d,1200,BLUE\r\n' % self.grating)

        elif funcname == 'getoutport':
            self.buf.append('0,%d\r\n' % self.outport)

        elif funcname == 'getwave':
            self.buf.append('0,%.3f\r\n' % self.wavelength)

        elif funcname == 'shutteropen':
            self.shutterOpen = True
            self.buf.append('0,O\r\n')

        elif funcname == 'shutterclose':
            self.shutterOpen = False
            self.buf.append('0,C\r\n')

        elif funcname == 'setgrating':
            self.grating = int(args[0])
            self.buf.append('0,%d,1200,BLUE\r\n' % self.grating)

        elif funcname == 'setoutport':
            self.outport = int(args[0])
            self.buf.append('0,%d\r\n' % self.outport)

        elif funcname == 'setwave':
            self.wavelength = float(args[0])
            self.buf.append('0,%.3f\r\n' % self.wavelength)

        else:
            self.buf.append('1,unknown command %s\r\n'%cmdStr)

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
