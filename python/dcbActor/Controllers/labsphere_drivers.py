class LabsphereTalk:
    def Attenuator(self, v):
        if (v < 0) or (v > 255):
            Exception("Error : Value must be within [0:255]")
        s = format(v, "08b")
        s3 = "P1"
        i = 1

        for l in s:
            if l == '0':
                s3 += 'J'
            else:
                s3 += 'K'
            s3 += str(i)
            i += 1

        coll = [(s3, 0.8), ("P2K3X", 0.5), ("P2K1K2", 0.8), ("P2J3X", 0.0)]

        return coll

    def Lamp(self, v):

        s = "P3J1X" if v else "P3K1X"

        return s

    def Lamp_on(self):
        return self._Lamp(True)

    def Lamp_off(self):
        return self._Lamp(False)

    def Read_Photodiode(self):
        return "O0X"

    def LabSphere_init(self):
        coll = [("Z1X", 0.2), ("A0X", 0.2), ("N1X", 0.2), ("H1X", 0.2), ("L1X", 0.2), ("F1X", 0.2),
                ("C2X", 0.2), ("P3X", 0.2), ("K1X", 0.2), ("P1J1J2J3J4J5J6J7J8", 0.5), ("P2K3X", 0.5),
                ("P2K1K2", 0.8), ("P2J3X", 0.8), ("P2K3X", 0.0)]
        return coll

    def Open(self):
        return self.Attenuator(255)

    def Close(self):
        return self.Attenuator(0)
