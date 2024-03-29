import socket
import time

import numpy as np


class Monosim(socket.socket):
    errorCodes = {0: 'Command not understood',
                  1: 'System error (miscellaneous)',
                  2: 'Bad parameter used in Command',
                  3: 'Destination position for wavelength motion not allowed',
                  4: 'OK',
                  5: 'OK',
                  6: 'Accessory not present (usually filter wheel)',
                  7: 'Accessory already in specified position',
                  8: 'Could not home wavelength drive',
                  9: 'Label too long',
                  10: 'OK'
                  }

    def __init__(self):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.sendall = self.fakeSend
        self.recv = self.fakeRecv

        self.buf = []
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

        elif funcname == 'geterror':
            error = self.errorCodes[np.random.randint(11)]
            self.buf.append('0,%s\r\n' % error)

        elif funcname == 'getshutter':
            shutter = 'O' if self.shutterOpen else 'C'
            self.buf.append('0,%s\r\n' % shutter)

        elif funcname == 'getgrating':
            self.buf.append('0,%d,1200,600.00\r\n' % self.grating)

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
            time.sleep(6)
            self.buf.append('0,%d,1200,600.00\r\n' % self.grating)

        elif funcname == 'setoutport':
            self.outport = int(args[0])
            self.buf.append('0,%d\r\n' % self.outport)

        elif funcname == 'setwave':
            self.wavelength = float(args[0])
            self.buf.append('0,%.3f\r\n' % self.wavelength)

        else:
            self.buf.append('1,unknown command %s\r\n' % cmdStr)

    def fakeRecv(self, buffer_size):
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
