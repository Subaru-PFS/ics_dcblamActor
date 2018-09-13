logic = {'0': 'K', '1': 'J'}


def attenuator(value):
    if not (0 <= value <= 255):
        raise ValueError('Value must be within [0:255]')

    bits = format(value, '08b')

    cmdStr = ''.join(['%s%i' % (logic[bit], len(bits) - i) for i, bit in enumerate(bits)])

    coll = [('P1%sX' % cmdStr, 0.5), ('K2K1X', 0.50), ('P2K3X', 0.5), ('P2J3X', 0.0)]

    return coll


def setLamp(boolean):
    cmdStr = 'P3J1X' if boolean else 'P3K1X'
    return cmdStr


def photodiode():
    return 'O0X'


def init():
    coll = [('L0X', 0.5),  # Remote control mode
            ('Z1X', 0.5),  # Turn off zero mdde
            ('A0X', 0.5),  # Auto ranging mode
            ('N1X', 0.5),  # Normalize mode
            ('H1X', 0.5),  # Display 4 digits
            ('F1X', 0.5),  # Turn off Digital filter
            ('C2X', 0.5),  # Default current mode
            ('P3K1X', 0)]  # switch lamp off

    return coll


def fullOpen():
    return attenuator(0)


def fullClose():
    return attenuator(255)
