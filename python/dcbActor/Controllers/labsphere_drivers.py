class LabsphereTalk(object):
    conv = {'0': 'K', '1': 'J'}

    def attenuator(self, value):
        if not (0 <= value <= 255):
            raise ValueError('Value must be within [0:255]')

        bits = format(value, '08b')

        cmdStr = ''.join(['%s%i' % (LabsphereTalk.conv[bit], len(bits) - i) for i, bit in enumerate(bits)])

        coll = [('P1%sX' % cmdStr, 1.0), ('K2K1X', 1.0), ('P2K3X', 1.0), ('P2J3X', 0.0)]

        return coll

    def setLamp(self, boolean):
        cmdStr = 'P3J1X' if boolean else 'P3K1X'
        return cmdStr

    def lampOn(self):
        return self.setLamp(True)

    def LampOff(self):
        return self.setLamp(False)

    def photodiode(self):
        return 'O0X'

    def init(self):
        coll = [('L0X', 1.0),  # Remote control mode
                ('Z1X', 1.0),  # Turn off zero mdde
                ('A0X', 1.0),  # Auto ranging mode
                ('N1X', 1.0),  # Normalize mode
                ('H1X', 1.0),  # Display 4 digits
                ('F1X', 1.0),  # Turn off Digital filter
                ('C1X', 1.0),  # Default current mode
                ('P3K1X', 0)]  # switch lamp off

        return coll

    def fullOpen(self):
        return self.attenuator(0)

    def fullClose(self):
        return self.attenuator(255)
