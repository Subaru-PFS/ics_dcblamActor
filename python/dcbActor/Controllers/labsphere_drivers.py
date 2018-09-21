logic = {'0': 'K', '1': 'J'}


def attenuator(value):
    if not (0 <= value <= 255):
        raise ValueError('Value must be within [0:255]')

    bits = format(value, '08b')

    cmdStr = ''.join(['%s%i' % (logic[bit], len(bits) - i) for i, bit in enumerate(bits)])

    coll = ['P1%sX' % cmdStr, 'P2K3K2K1X', 'P2J3X']

    return coll


def turnQth(state):
    if state in [True, 'on']:
        cmdStr = 'P3J1X'
    elif state in [False, 'off']:
        cmdStr = 'P3K1X'
    else:
        raise ValueError('%s does not exist' % state)

    return cmdStr


def photodiode():
    return 'O0X'


def init():
    coll = ['L0X',  # Remote control mode
            'Z1X',  # Turn off zero mdde
            'A0X',  # Auto ranging mode
            'N1X',  # Normalize mode
            'H1X',  # Display 4 digits
            'F1X',  # Turn off Digital filter
            'C2X',  # Default current mode
            'P3K1X']  # switch lamp off

    return coll


def fullOpen():
    return attenuator(0)


def fullClose():
    return attenuator(255)
