"""Single source of truth for every part: value, footprint, LCSC code, notes.

The schematic, the BOM, the CPL, the cost estimate and the silkscreen legends
are all generated from this table, so there is exactly one place to change a
part.  Stock figures are what JLCPCB's parts API returned on STOCK_DATE;
`scripts/jlc_api.py <code>` re-queries them, and the release refuses to build
when a code's description no longer matches the value and package here.

Values that the design arithmetic chooses (the filters, the gains, the
timers) are not typed here: sim/design.py picks them from PASSIVES and writes
sim/design.json, which the schematic generator reads.
"""

REV = "A"
BOARD_DATE = "2026-11-02"
BOARD_NAME = "Earth's Field NMR"
PROJECT_URL = "github.com/gallicchio/earth-nmr-pcb"   # the git remote of this checkout
STOCK_DATE = "2026-11-02"

# lcsc       : JLCPCB / LCSC order code
# jlc_type   : "basic" | "preferred" | "extended"  (Extended = per-part setup fee)
# process    : "SMT" | "THT"
# stock      : stock seen at JLCPCB on STOCK_DATE
# alt        : drop-in alternates, checked to share the footprint
PARTS = {
    # ---- every op-amp on the board: one part number, one per triangle ------
    # OPA197 (TI): 36 V CMOS, rail to rail in and out, 5.5 nV/rtHz at 1 kHz and
    # essentially no current noise (the tank's resonant resistance is 10-30 k,
    # so a bipolar op-amp's pA/rtHz would be the noise floor), 10 MHz.
    # DBV pinout (datasheet Fig. "DBV Package"): 1 OUT, 2 V-, 3 +IN, 4 -IN, 5 V+.
    "OPAMP": dict(
        value="OPA197", mpn="OPA197IDBVR", lcsc="C221351", jlc_type="extended",
        process="SMT", stock=85610, price=0.7005,
        footprint="Package_TO_SOT_SMD:SOT-23-5",
        symbol="Amplifier_Operational:OPA197xDBV",
        pins={"OUT": "1", "V-": "2", "+IN": "3", "-IN": "4", "V+": "5"},
        desc="OPA197IDBVR (TI): 36 V CMOS op-amp, 5.5 nV/rtHz at 1 kHz, fA input current, "
             "10 MHz, rail-to-rail in and out, SOT-23-5.  All seven amplifiers, one per "
             "triangle, so the silkscreen is the schematic",
        alt=["OPA196IDBVR / C2060757 (118 in stock, 15 nV/rtHz: fine after the first stage)"]),
    # ---- the three comparators of the sequencer -----------------------------
    # TS391ILT (ST): pinout 1 OUT, 2 VCC-, 3 IN-, 4 IN+, 5 VCC+ -- the same pads
    # as the OPA197 except the two inputs, which are swapped.  The TS391RILT is
    # a different pinout; the code below is the ILT.
    "COMP": dict(
        value="TS391", mpn="TS391ILT", lcsc="C71896", jlc_type="extended",
        process="SMT", stock=14931, price=0.1382,
        footprint="Package_TO_SOT_SMD:SOT-23-5",
        symbol="earthnmr:TS391",
        pins={"OUT": "1", "V-": "2", "-IN": "3", "+IN": "4", "V+": "5"},
        desc="TS391ILT (ST): single comparator, 2-36 V, open-collector output, inputs to "
             "ground, SOT-23-5 (1 OUT, 2 V-, 3 IN-, 4 IN+, 5 V+).  The POLARIZE IN level "
             "detector, the gate delay and the relay hold",
        alt=["LM397MFX/NOPB / C132076 (22k, 30 V): a different pinout, 1 IN+? -- check "
             "before substituting"]),
    # ---- the free-running timer ---------------------------------------------
    "TIMER": dict(
        value="NE555", mpn="NE555DR", lcsc="C7593", jlc_type="preferred",
        process="SMT", stock=136602, price=0.1083,
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        symbol="Timer:NE555D",
        desc="NE555DR (TI) bipolar 555 timer, 4.5-16 V, SOIC-8: the INT sequencer, an "
             "astable with diode-steered charge and discharge so POLARIZE and LISTEN "
             "set independently",
        alt=["NE555DTR (XBLW) / C18723595 (191k)"]),
    # ---- the polarizing switch -----------------------------------------------
    # IRFS4227 (Infineon): 200 V, 26 mohm at 10 V, D2PAK, avalanche rated.  The
    # TVS clamps its drain at about 125 V while the coil's current ramps down.
    "MOSFET": dict(
        value="IRFS4227", mpn="IRFS4227TRLPBF", lcsc="C146578", jlc_type="extended",
        process="SMT", stock=6562, price=0.8286,
        footprint="Package_TO_SOT_SMD:TO-263-2",
        symbol="Transistor_FET:Q_NMOS_GDS",
        desc="IRFS4227TRLPBF (Infineon): N-channel MOSFET, 200 V, 62 A, 26 mohm at "
             "VGS = 10 V, Qg 98 nC, D2PAK (1 = G, 2 = D on the tab, 3 = S): switches "
             "the coil's polarizing current, up to 3 A",
        alt=["IRF640NSTRLPBF / C23708 (51.9k, 200 V 150 mohm: 1.4 W at 3 A, warmer)"]),
    # ---- the T/R relay: polarize or listen ------------------------------------
    # Hongfa HFD3/12: DPDT (2 Form C), AgNi + gold, bifurcated contacts (the
    # listening path carries microvolts), 3 A at 30 VDC, 4 ms operate and
    # release, 1028 ohm coil, 9 V to pull in, 24 V maximum.  The pins are the
    # industry-standard 2 Form C layout (Omron G6S-2): coil 1 (+) and 12 (-),
    # pole A common 4, normally closed 3, normally open 5; pole B common 9,
    # normally closed 10, normally open 8 (datasheet, "Wiring diagram, bottom view").
    "RELAY": dict(
        value="HFD3/12", mpn="HFD3/12", lcsc="C329305", jlc_type="extended",
        process="THT", stock=4716, price=1.3894,
        footprint="Relay_THT:Relay_DPDT_Omron_G6S-2",
        symbol="earthnmr:HFD3_Split",
        desc="Hongfa HFD3/12 DPDT signal relay, 12 V 1028 ohm coil (9 V to pull in, 24 V "
             "max), AgNi + Au bifurcated contacts, 3 A 30 VDC, 4 ms: released, the coil is "
             "the receiver's; energized, the polarizing current's.  Pins as the Omron G6S-2",
        alt=["G6S-2 DC12 (Omron) / C1525289 (12.6k, 2 A: limits the coil current to 2 A)"]),
    # ---- small transistors and diodes -----------------------------------------
    "NPN": dict(
        value="MMBT3904", mpn="MMBT3904", lcsc="C20526", jlc_type="basic",
        process="SMT", stock=2658848, price=0.0117,
        footprint="Package_TO_SOT_SMD:SOT-23",
        symbol="Transistor_BJT:Q_NPN_BEC",
        desc="MMBT3904 NPN, SOT-23 (1 B, 2 E, 3 C): the relay's coil driver and the SYNC "
             "OUT follower"),
    "DSIG": dict(
        value="1N4148W", mpn="1N4148W", lcsc="C81598", jlc_type="basic",
        process="SMT", stock=3765724, price=0.0124,
        footprint="Diode_SMD:D_SOD-123", symbol="Device:D",
        desc="1N4148W, SOD-123 (1 = cathode): the timer's steering diodes, the delays' "
             "bypass diodes, the relay coil's freewheel diode"),
    "DCLAMP": dict(
        value="BAV99", mpn="BAV99,215", lcsc="C2500", jlc_type="basic",
        process="SMT", stock=1335787, price=0.0111,
        footprint="Package_TO_SOT_SMD:SOT-23", symbol="Diode:BAV99",
        desc="BAV99 two diodes in series, SOT-23 (1 = A1, 2 = K2, 3 = K1/A2): clamps "
             "POLARIZE IN's comparator input to ground and +15 V"),
    "DSCH": dict(
        value="SS34", mpn="SS34", lcsc="C8678", jlc_type="basic",
        process="SMT", stock=3348396, price=0.0352,
        footprint="Diode_SMD:D_SMA", symbol="Device:D_Schottky",
        desc="SS34 3 A 40 V Schottky, SMA (1 = cathode): in series with each analog "
             "supply (a reversed supply does nothing), the rail clamps, and the "
             "polarizing supply's reverse-polarity crowbar (a reversed supply trips F1)"),
    # ---- TVS diodes -------------------------------------------------------------
    "TVS_CLAMP": dict(
        value="SMCJ100A", mpn="SMCJ100A", lcsc="C42371542", jlc_type="preferred",
        process="SMT", stock=19026, price=0.0916,
        footprint="Diode_SMD:D_SMC", symbol="Device:D_Zener",
        desc="SMCJ100A unidirectional TVS, 1.5 kW (10/1000 us), 100 V standoff, "
             "111-123 V breakdown, 162 V at 9.3 A, SMC (1 = cathode): from the MOSFET's "
             "drain to its source.  It holds the coil's flyback at about 125 V, so the "
             "current falls to zero in a straight line in a millisecond or two: a sudden "
             "switch-off, which leaves the magnetization behind to precess"),
    "TVS_TANK": dict(
        value="SMBJ12CA", mpn="SMBJ12CA", lcsc="C353397", jlc_type="extended",
        process="SMT", stock=209161, price=0.0409,
        footprint="Diode_SMD:D_SMB", symbol="Device:D_TVS",
        desc="SMBJ12CA bidirectional TVS, 600 W, 12 V standoff, 19.9 V at 30 A, 390 pF, "
             "SMB: across the tank.  Idle (the tank carries microvolts) unless the relay "
             "ever lets go with coil current still flowing: then it takes the coil's "
             "energy instead of the capacitors and the preamplifier"),
    "TVS_SUPPLY": dict(
        value="SMBJ33A", mpn="SMBJ33A", lcsc="C353366", jlc_type="extended",
        process="SMT", stock=62111, price=0.0404,
        footprint="Diode_SMD:D_SMB", symbol="Device:D_Zener",
        desc="SMBJ33A unidirectional TVS, 600 W, 33 V standoff, 53 V at 11 A, SMB "
             "(1 = cathode): across the polarizing supply, for the spike a hot-plugged "
             "bench lead rings to"),
    "PTC": dict(
        value="3A", mpn="2920L300/36GR", lcsc="C22435908", jlc_type="extended",
        process="SMT", stock=15157, price=0.1851,
        footprint="Fuse:Fuse_2920_7451Metric", symbol="Device:Polyfuse",
        desc="LUTE resettable fuse 2920L300/36GR: 3 A hold, 5 A trip, 36 V, 12-48 mohm, "
             "2920: in the polarizing supply's + lead, ahead of everything"),
    # ---- the sense resistor -----------------------------------------------------
    "RSENSE": dict(
        value="0.1R", mpn="RLP25FEER100", lcsc="C160587", jlc_type="extended",
        process="SMT", stock=114970, price=0.0571,
        footprint="Resistor_SMD:R_2512_6332Metric", symbol="Device:R_US",
        desc="0.1 ohm 1 % 2 W 50 ppm/K current-sense resistor, 2512: the polarizing "
             "current's return, so I POL reads 0.1 V per ampere (0.9 W at 3 A)"),
    # ---- the tuning bank's switch -----------------------------------------------
    "DIP8": dict(
        value="SW_DIP_x08", mpn="DSIC08LSGET", lcsc="C3293158", jlc_type="extended",
        process="SMT", stock=5122, price=0.4889,
        footprint="earthnmr:SW_DIP_SPSTx08_Slide_KingTek_DSIC08LSGET_W8.61mm_P2.54mm",
        symbol="Switch:SW_DIP_x08",
        desc="KingTek DSIC08LSGET 8-way DIP switch, SMD, 2.54 mm, raised sliders: each "
             "switch adds one binary weight of C0G capacitance to the tank",
        alt=["DSIC08LSGET / C54953 (2315 in stock, the same part)"]),
    # ---- slide switches ---------------------------------------------------------
    "SW": dict(
        value="SW_SPDT", mpn="MSK12C02", lcsc="C431540", jlc_type="extended",
        process="SMT", stock=194273, price=0.0544,
        footprint="earthnmr:SW_SPDT_Shouhan_MSK12C02",
        symbol="Switch:SW_SPDT",
        desc="SPDT slide switch, SMD, 2 = common; the knob slides toward the pin it "
             "connects.  SEQUENCE, MODE and GAIN"),
    # ---- trimmers: the two times ------------------------------------------------
    "TRIM": dict(
        value="2M", mpn="3362P-1-205", lcsc="C48997907", jlc_type="extended",
        process="THT", stock=9203, price=0.2394,
        footprint="earthnmr:Potentiometer_Bourns_3362P_Vertical",
        symbol="Device:R_Potentiometer_Trim_US",
        desc="3362P 2 M single-turn cermet trimmer, top adjust (Bourns' pattern and "
             "pinout: the wiper reaches 3 turning clockwise): POLARIZE TIME and LISTEN "
             "TIME, each a rheostat between 1 and 2 with 3 tied to the wiper, so "
             "clockwise is longer",
        alt=["3362P-1-205LF / C49190490 (18.4k, $0.33)"]),
    # ---- capacitors that are not plain 0805 passives ------------------------------
    "CFILM": dict(
        value="1uF", mpn="MES105J2A-7-50R0", lcsc="C333829", jlc_type="extended",
        process="THT", stock=51902, price=0.1387,
        footprint="earthnmr:C_Film_P5.00mm_L7.2mm_W6.0mm",
        symbol="Device:C",
        desc="1 uF 5 % 100 V metallized polypropylene film, leads on 5 mm: the 555's "
             "timing capacitor (two in parallel).  Film, not X7R: its value does not move "
             "with the voltage the timer swings it through"),
    "CBULK": dict(
        value="100uF", mpn="JVJ25V100M6x5", lcsc="C46550402", jlc_type="extended",
        process="SMT", stock=200110, price=0.0423,
        footprint="Capacitor_SMD:CP_Elec_6.3x5.4",
        symbol="Device:C_Polarized_US",
        desc="100 uF 25 V aluminium electrolytic, SMD 6.3 x 5.4 mm: one on each analog rail"),
    "CPOL": dict(
        value="470uF", mpn="EFVM050ADA471M10C0", lcsc="C22469994", jlc_type="extended",
        process="SMT", stock=51190, price=0.1755,
        footprint="Capacitor_SMD:CP_Elec_10x12.5",
        symbol="Device:C_Polarized_US",
        desc="470 uF 50 V aluminium electrolytic, SMD 10 x 12.5 mm: the polarizing "
             "supply's reservoir at the board, which damps a hot-plugged lead's ringing"),
    # ---- connectors -------------------------------------------------------------
    "BNC": dict(
        value="BNC", mpn="BNC-KYWE-295-W4-N", lcsc="C41416668", jlc_type="extended",
        process="THT", stock=215, price=1.2929,
        footprint="earthnmr:BNC_KYWE_RightAngle",
        symbol="Connector:Conn_Coaxial",
        desc="50 ohm BNC jack, right angle, 4 ground posts on 8x8 mm (the op-amp and "
             "PID boards' jack: JLCPCB rotation +90 read off the Lorenz board's preview)",
        alt=["HL2-BNC-KYWE / C48606310 (107 in stock)"]),
    "TERM3": dict(
        value="Screw_Terminal_01x03", mpn="KF301-5.0-3P", lcsc="C474882",
        jlc_type="extended", process="THT", stock=28051, price=0.1396,
        footprint="earthnmr:TerminalBlock_KF301_1x03_P5.00mm",
        symbol="Connector:Screw_Terminal_01x03",
        desc="3-way 5.0 mm screw terminal block, 17 A: POWER (+15 V, GND, -15 V) and COIL "
             "(A, B, shield)"),
    "TERM2": dict(
        value="Screw_Terminal_01x02", mpn="KF301-5.0-2P", lcsc="C474881",
        jlc_type="extended", process="THT", stock=53579, price=0.1019,
        footprint="earthnmr:TerminalBlock_KF301_1x02_P5.00mm",
        symbol="Connector:Screw_Terminal_01x02",
        desc="2-way 5.0 mm screw terminal block, 17 A: the POLARIZING SUPPLY"),
    # ---- probe loops --------------------------------------------------------------
    "TP": dict(
        value="", mpn="RH-5019", lcsc="C5199800", jlc_type="extended",
        process="SMT", stock=101462, price=0.0966,
        footprint="earthnmr:TestPoint_Loop_RH-5019",
        symbol="Connector:TestPoint",
        desc="SMT test loop, 3.8 x 2.0 mm wire loop on one pad (Keystone 5019 style): "
             "a scope probe's hook or a mini-grabber clips onto it"),
    "LED": dict(
        value="GREEN", mpn="KT-0805G", lcsc="C2297", jlc_type="basic",
        process="SMT", stock=2420908, price=0.0164,
        footprint="LED_SMD:LED_0805_2012Metric", symbol="Device:LED",
        desc="green 0805 LED: each analog rail, and the polarizing supply"),
    "LED_R": dict(
        value="RED", mpn="NCD0805R1", lcsc="C84256", jlc_type="basic",
        process="SMT", stock=3082781, price=0.0135,
        footprint="LED_SMD:LED_0805_2012Metric", symbol="Device:LED",
        desc="red 0805 LED across the relay's coil: lit while the board polarizes"),
    # ---- plain footprints --------------------------------------------------------
    "R_0805": dict(footprint="Resistor_SMD:R_0805_2012Metric", process="SMT",
                   symbol="Device:R_US"),
    "C_0805": dict(footprint="Capacitor_SMD:C_0805_2012Metric", process="SMT",
                   symbol="Device:C"),
    "C_1206": dict(footprint="Capacitor_SMD:C_1206_3216Metric", process="SMT",
                   symbol="Device:C"),
    "MH": dict(value="", process="THT", in_bom=False,
               footprint="MountingHole:MountingHole_3.2mm_M3",
               symbol="Mechanical:MountingHole",
               desc="M3 mounting hole, one per corner"),
}

# Resistor and capacitor order codes, keyed by the value printed on the sheet.
# Every resistor is UniOhm 0805 1 % thick film (150 V, 0.125 W): Basic or Preferred.
_R = "0805 1% 125mW thick film"
PASSIVES = {
    "1M":    dict(lcsc="C17514", mpn="0805W8F1004T5E", jlc_type="basic", price=0.0044, stock=1917417, note=_R),
    "270k":  dict(lcsc="C17589", mpn="0805W8F2703T5E", jlc_type="preferred", price=0.0059, stock=122300, note=_R),
    "220k":  dict(lcsc="C17556", mpn="0805W8F2203T5E", jlc_type="basic", price=0.0030, stock=382494, note=_R),
    "200k":  dict(lcsc="C17539", mpn="0805W8F2003T5E", jlc_type="basic", price=0.0056, stock=529881, note=_R),
    "180k":  dict(lcsc="C17501", mpn="0805W8F1803T5E", jlc_type="preferred", price=0.0034, stock=53984, note=_R),
    "150k":  dict(lcsc="C17470", mpn="0805W8F1503T5E", jlc_type="basic", price=0.0049, stock=705172, note=_R),
    "100k":  dict(lcsc="C149504", mpn="0805W8F1003T5E", jlc_type="basic", price=0.0060, stock=3058790, note=_R),
    "62k":   dict(lcsc="C17783", mpn="0805W8F6202T5E", jlc_type="preferred", price=0.0019, stock=221572, note=_R),
    "56k":   dict(lcsc="C17756", mpn="0805W8F5602T5E", jlc_type="preferred", price=0.0030, stock=299304, note=_R),
    "24k":   dict(lcsc="C17575", mpn="0805W8F2402T5E", jlc_type="basic", price=0.0044, stock=314882, note=_R),
    "20k":   dict(lcsc="C4328", mpn="0805W8F2002T5E", jlc_type="basic", price=0.0042, stock=1735754, note=_R),
    "15k":   dict(lcsc="C17475", mpn="0805W8F1502T5E", jlc_type="basic", price=0.0059, stock=679379, note=_R),
    "10k":   dict(lcsc="C17414", mpn="0805W8F1002T5E", jlc_type="basic", price=0.0034, stock=52272724, note=_R),
    "9.1k":  dict(lcsc="C17855", mpn="0805W8F9101T5E", jlc_type="preferred", price=0.0030, stock=292599, note=_R),
    "8.2k":  dict(lcsc="C17828", mpn="0805W8F8201T5E", jlc_type="basic", price=0.0027, stock=453908, note=_R),
    "4.7k":  dict(lcsc="C17673", mpn="0805W8F4701T5E", jlc_type="basic", price=0.0039, stock=4295547, note=_R),
    "3.3k":  dict(lcsc="C26010", mpn="0805W8F3301T5E", jlc_type="basic", price=0.0043, stock=1596593, note=_R),
    "2.2k":  dict(lcsc="C17520", mpn="0805W8F2201T5E", jlc_type="basic", price=0.0050, stock=3421350, note=_R),
    "1k":    dict(lcsc="C17513", mpn="0805W8F1001T5E", jlc_type="basic", price=0.0035, stock=42005472, note=_R),
    "200R":  dict(lcsc="C17540", mpn="0805W8F2000T5E", jlc_type="basic", price=0.0068, stock=996348, note=_R),
    "100R":  dict(lcsc="C17408", mpn="0805W8F1000T5E", jlc_type="basic", price=0.0042, stock=7732481, note=_R),
    "51R":   dict(lcsc="C17738", mpn="0805W8F510JT5E", jlc_type="basic", price=0.0030, stock=677677, note=_R),
    "47R":   dict(lcsc="C17714", mpn="0805W8F470JT5E", jlc_type="basic", price=0.0029, stock=746039, note=_R),
    # capacitors: C0G wherever a value sets a frequency or a time, X7R for bypass only
    "100nF": dict(lcsc="C49678", mpn="CC0805KRX7R9BB104", jlc_type="basic",
                  price=0.0205, stock=22485395, note="X7R 50 V 0805: supply bypass only"),
    "10nF":  dict(lcsc="C237168", mpn="0805N103J500CT", jlc_type="extended",
                  price=0.0302, stock=24010, note="C0G 50 V 5 % 0805: the high-pass filters, the bank, the 555's CTRL"),
    "6.8nF": dict(lcsc="C326913", mpn="CC0805JKNPO9BN682", jlc_type="extended",
                  price=0.0904, stock=5540, note="C0G 50 V 5 % 0805: the low-pass filter, the bank"),
    "3.3nF": dict(lcsc="C880847", mpn="0805N332J101CT", jlc_type="extended",
                  price=0.0214, stock=9192, note="C0G 100 V 5 % 0805: the low-pass filter, the bank"),
    "47nF":  dict(lcsc="C20617849", mpn="C1206N473J101T", jlc_type="extended",
                  price=0.2002, stock=1765, note="C0G 100 V 5 % 1206: the bank", footprint="C_1206"),
    "100nF_C0G": dict(lcsc="C170182", mpn="1206N104J500CT", jlc_type="extended",
                      price=0.1580, stock=153887, note="C0G 50 V 5 % 1206: the bank and the two delays",
                      footprint="C_1206"),
}

# The value each passive key prints on the board and the sheet.
PRINT = {"100nF_C0G": "100nF"}


def printed(key):
    return PRINT.get(key, key)


# --------------------------------------------------------- JLCPCB rotations
# (degrees counter-clockwise to ADD to the KiCad rotation, (dx, dy) in mm to
# ADD to the CPL point in the footprint's own unrotated frame with y UP, how
# known, note).  "read": seen in a JLCPCB preview on a real order of one of
# Jason's boards.  "predicted": from fitting their land pattern on ours by pin
# number (scripts/check_rotations.py); listed in PLACEMENT_CHECKS.txt.
JLC_ROTATION = {
    "C41416668": (90, (0, 0), "read", "BNC-KYWE-295-W4-N: Lorenz board rev A/B preview, built and working"),
    "C221351": (180, (0, 0), "predicted", "SOT-23-5: +180 read on 59 SOT-23-5 placements on the GPSDO board"),
    "C71896": (180, (0, 0), "predicted", "SOT-23-5: +180 read on 59 SOT-23-5 placements on the GPSDO board"),
    "C2297": (0, (0, 0), "read", "KT-0805G on KiCad's LED_0805: GPiBridge rev A preview, cathode at pad 1"),
    "C84256": (0, (0, 0), "read", "NCD0805R1 on KiCad's LED_0805: GPiBridge rev A preview, cathode at pad 1"),
    "C8678": (0, (0, 0), "predicted", "SS34 SMA: cathode (pad 1) at -x in both drawings"),
    "C5199800": (0, (0, 0), "predicted", "RH-5019 test loop: one 4.0 x 2.2 pad"),
}
