KeysDictionary('dcb', (1, 1),
               Key("text", String(help="text for humans")),
               Key("version", String(help="EUPS/git version")),
               Key("ne", Bool("off", "on", name='neon', help='neon lamp switch')),
               Key("xenon", Bool("off", "on", name='xenon', help='xenon lamp switch')),
               Key("hgar", Bool("off", "on", name='hgar', help='Hg-Ar switch')),
               Key("deuterium", Bool("off", "on", name='deuterium', help='deuterium lamp switch')),
               Key("pow_attenuator", Bool("off", "on", name='pow_attenuator', help='power attenuator switch')),
               Key("pow_sphere", Bool("off", "on", name='pow_sphere', help='power int sphere switch')),
               Key("pow_halogen", Bool("off", "on", name='pow_halogen', help='power halogen switch')),

               Key("photodiode", Float(invalid="Nan", help='photo diode flux (foot-lambert)')),
               Key("attenuator", UInt(help='attenuator opening value (close=0)')),
               Key("halogen", Bool("off", "on", name='halogen', help='halogen switch')),

               )
