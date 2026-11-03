"""The board, as a drawing: where every part sits and where every wire runs.

The board is the schematic.  The POLARIZING SUPPLY comes in at the top left
and runs along the top to the relay; the COIL comes in at the left edge to
the relay's commons, and the coil's two leads close a loop round the
POLARIZING SWITCH (the MOSFET, its clamp, the sense resistor); to the right
the relay's driver, the TANK (the clamp, the tuning DIP and its binary
columns of C0G capacitance) and the signal row: PREAMPLIFIER, HIGH-PASS,
LOW-PASS, GAIN, OUT at the right edge.  Along the bottom the SEQUENCER;
POWER at the top right.

Coordinates are millimetres from the board's top-left corner, y down;
rotations are KiCad's, degrees counter-clockwise.  Conventions (checked
against pcbnew's own pad positions):
  0805/1206/SOD-123/SMA/SMB/SMC at rot 0: pad 1 left; 90: pad 1 at the bottom;
    270: pad 1 on top.  Diodes and LEDs: pad 1 the cathode.
  SOT-23-5 (op-amps, comparators) at rot 270 only: pads 3, 2, 1 along the top,
    4, 5 along the bottom (gen_pcb.oa_geometry draws the triangle; the + of an
    OPA197 and the - of a TS391 enter its left edge at cy - OA_IN).
  SOT-23 NPN at rot 90: collector up, base lower-left, emitter lower-right;
    the BAV99 at rot 90: the common (3) on top, 1 and 2 below.
  HFD3 (Omron G6S-2 pattern) at rot 270, origin on pin 1: the top row is
    5 4 3 . 1 (NO, COM, NC of pole A, the coil's +) at x -10.16 -7.62 -5.08 0,
    the bottom row 8 9 10 . 12 (pole B, the coil's -), 5.08 below.
  TO-263-2 at rot 90: the tab (drain) up, gate lower-left, source lower-right.
  KF301 at rot 90: pins in a column, pin 1 at the bottom, wires from -x; at 0:
    pins along x, pin 1 left, wires from -y.
  BNC at 0: barrel to +x; 90: to -y (top edge); 270: to +y (bottom edge); the
    centre 5.6 from the edge (the shell pads 0.3 inside it).
  MSK12C02 at 0: pins 1, 2, 3 at x -2.25, +0.75, +2.25 along the top; at 180
    along the bottom, 1 on the right.
  SOIC-8 at 0: pins 1-4 down the left, 8-5 down the right.
  3362P at 180: the wiper (2) at the bottom, 3 and 1 above it, the body above.

A wire is ([point, ...], width); a point is (x, y) or ("REF", "pad"), which
the board generator resolves to the pad's centre (or where a drawn symbol's
lead leaves it) and whose net it takes.  Planes carry ground, +15 V and
-15 V: those pads get vias, not wires (VIA_AT steers a via where the search
would not put it; MULTI_VIAS gives the polarizing current's ground pads
several big ones; MARKS draws a ground symbol or rail flag at a through-hole
pin that reaches its plane by itself).
"""
import json, math, os
import parts

D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sim", "design.json")))

W_SIG, W_POL, W_COIL = 0.35, 2.0, 1.5          # signals, the polarizing current, the coil's leads
OA_IN = 2.5                                     # an op-amp's inputs enter its triangle at cy -/+ OA_IN
OA_H, OA_W = 12.0, 10.0
BOARD_H = 150.0
BNC_IN = 5.6                                    # a BNC's centre from the edge it faces

PLACE = {}
WIRES = []
HOPS = []
VIA_AT = {}
MULTI_VIAS = {}
FIELD_AT = {}
TEXTS = []
BOXES = []
SILK_LINES = []
SILK_DOTS = []
MARKS = []
HIDE_REF, HIDE_VALUE = set(), set()
TP_LABEL = {}
SOLID_PADS = []
NO_MARK = set()
OPAMPS = ["U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "U10", "U12"]
TRANSISTORS = {"Q2": ("NPN", "left"), "Q3": ("NPN", "left")}
UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def P(ref, x, y, rot=0):
    PLACE[ref] = (round(float(x), 4), round(float(y), 4), rot)


def W(width, *points):
    WIRES.append((list(points), width))


def T(x, y, txt, size=0.8, just="left", angle=0, thick=None):
    TEXTS.append((x, y, txt, size, thick or (0.15 if size < 1.2 else 0.2), just, angle))


def hide(*refs):
    for r in refs:
        HIDE_REF.add(r)
        HIDE_VALUE.add(r)


def bypass(ref_p, ref_m, cx, cy):
    """An op-amp's two 100 nF, hung from its supply vias (gen_pcb.oa_geometry:
    V+ 1.5 mm below pad 5, V- 1.5 mm above pad 2): the +15 V one under the
    triangle, the -15 V one over it, each with its ground via to the right and
    the rail's name printed by it (a comparator has only the first: its V- is
    ground)."""
    P(ref_p, cx + 0.95 + 0.91, cy + 4.3, 0)
    VIA_AT[(ref_p, "1")] = (cx + 0.95, cy + 2.64)
    VIA_AT[(ref_p, "2")] = RIGHT
    NO_MARK.add((ref_p, "1"))
    T(cx + 0.95, cy + 5.8, "+15", 0.8, "center")
    hide(ref_p)
    if ref_m:
        P(ref_m, cx + 0.91, cy - 4.3, 0)
        VIA_AT[(ref_m, "1")] = (cx, cy - 2.64)
        VIA_AT[(ref_m, "2")] = RIGHT
        NO_MARK.add((ref_m, "1"))
        T(cx, cy - 5.8, "-15", 0.8, "center")
        hide(ref_m)


def opamp(ref, cx, cy):
    """An op-amp or comparator at rot 270, its reference inside the triangle."""
    P(ref, cx, cy, 270)
    FIELD_AT[ref] = ((-2.4, 0.0, "center"), None)


# ===================================================== POLARIZING SUPPLY =====
P("J2", 4.6, 14.0, 90)                         # pin 2 (-, ground) at y 11.5, pin 1 (+) at 16.5
MARKS.append(("gnd", "J2", "2", 1, 0))
VB = 16.5                                      # the polarizing supply's bus
P("F1", 16.5, VB, 0)
FIELD_AT["F1"] = ((0.0, -3.6, "center"), (0.0, 3.6, "center"))
hide("J2", "J3")
W(W_POL, ("J2", "1"), ("F1", "1"))
KX, KY = 52.0, 44.0                            # the relay, by its pin 1
DROP_X = KX - 10.16                            # down to pole A's normally-open contact
W(W_POL, ("F1", "2"), (DROP_X, VB), ("K1", "5"))
P("D5", 23.5, 21.0, 270)                       # the crowbar: cathode on V POL
W(W_POL, (23.5, VB), ("D5", "1"))
MULTI_VIAS[("D5", "2")] = [(22.6, 25.6), (24.4, 25.6)]
FIELD_AT["D5"] = ((0.0, 7.0, "center"), (0.0, 8.2, "center"))
P("D6", 29.5, 21.5, 270)                       # the hot-plug clamp
W(1.0, (29.5, VB), ("D6", "1"))
MULTI_VIAS[("D6", "2")] = [(28.6, 26.4), (30.4, 26.4)]
FIELD_AT["D6"] = ((0.0, 7.5, "center"), (0.0, 8.7, "center"))
P("R3", 35.5, 20.0, 270)                       # the V POL lamp
W(W_SIG, (35.5, VB), ("R3", "1"))
P("LED3", 35.5, 24.0, 90)
W(W_SIG, ("R3", "2"), ("LED3", "2"))
VIA_AT[("LED3", "1")] = DOWN
P("C5", 28.5, 8.2, 90)                         # the reservoir, + down to the bus
FIELD_AT["C5"] = ((6.2, -0.7, "left"), (6.2, 0.7, "left"))
W(W_POL, ("C5", "1"), (28.5, VB))
MULTI_VIAS[("C5", "2")] = [(22.4, 4.0), (34.6, 4.0)]
P("TP1", 37.5, 12.0, 0)
W(W_SIG, (37.5, VB), ("TP1", "1"))
SOLID_PADS += [("J2", "1"), ("J2", "2")]

# =================================================== the COIL and the RELAY ==
CHAN = KY + 2.54                               # the channel between the relay's two rows
P("J3", 4.6, CHAN, 90)                         # pin 3 (shield) 5 above, 2 on the channel, 1 5 below
MARKS.append(("gnd", "J3", "3", 1, 0))
P("K1", KX, KY, 270)
MARKS.append(("+15", "K1", "1", 1, 0, 0.9))
FIELD_AT["K1"] = ((-11.4, -4.8, "right"), (-11.4, -3.6, "right"))
for (pin, dx, dy) in (("5", -10.16, 0), ("4", -7.62, 0), ("3", -5.08, 0), ("1", 0, 0),
                      ("8", -10.16, 5.08), ("9", -7.62, 5.08), ("10", -5.08, 5.08), ("12", 0, 5.08)):
    T(KX + dx - 1.3, KY + dy + (-2.2 if dy == 0 else 2.2), pin, 0.8, "center")
for i, ln in enumerate(("K1 at rest: the coil on", "the tank (4-3, 9-10);", "energized: on V POL and",
                        "Q1 (4-5, 9-8)")):
    T(43.4, 27.6 + 1.45 * i, ln, 0.8)

# the coil's A lead straight along the channel to pole A's common; its B lead
# down the left, along the bottom and up to pole B's: the two close a loop
# round the polarizing switch
YB = 82.0                                      # the loop's bottom
CBX = 47.5                                     # its right side, under pole B's NC
W(W_COIL, ("J3", "2"), (KX - 7.62, CHAN), ("K1", "4"))
W(W_COIL, ("J3", "1"), (10.5, CHAN + 5.0), (10.5, YB), (CBX, YB), (CBX, KY + 8.6),
  (KX - 7.62, KY + 8.6), ("K1", "9"))
SOLID_PADS += [("J3", "1"), ("J3", "2")]

# ===================================================== POLARIZING SWITCH =====
QX, QY = 32.4, 59.0
P("Q1", QX, QY, 90)                            # the tab (drain): x 27.0-37.8, y 52.8-62.2
FIELD_AT["Q1"] = ((-7.5, 1.6, "right"), (-7.5, 2.8, "right"))
T(QX - 2.54 - 1.4, QY + 9.3, "G", 0.8, "center")
T(QX + 2.54 + 1.4, QY + 9.3, "S", 0.8, "center")
T(QX + 7.2, QY - 3.6, "D", 0.8, "center")
DRN_X = KX - 10.16                             # pole B's normally-open contact, straight down
TAB_Y = QY - 1.5
P("D7", DRN_X, TAB_Y + 6.9, 270)               # the clamp: cathode on the drain, top
FIELD_AT["D7"] = ((2.9, -6.4, "center"), (4.5, 0.0, "center", 90))
W(W_POL, ("K1", "8"), (DRN_X, TAB_Y), ("D7", "1"))
W(W_POL, ("Q1", "2"), (DRN_X, TAB_Y))
P("TP2", 21.0, TAB_Y, 0)
TP_LABEL["TP2"] = (-2.6, 0.0, "right")
W(W_SIG, ("Q1", "2"), ("TP2", "1"))
SRC_Y = 71.0
W(W_POL, ("Q1", "3"), (QX + 2.54, SRC_Y), (DRN_X, SRC_Y), ("D7", "2"))
P("R4", 38.6, 74.6, 270)                       # the sense resistor, 0.1 ohm: pad 1 on the source line
FIELD_AT["R4"] = ((2.4, -0.7, "left"), (2.4, 0.7, "left"))
W(W_POL, (38.6, SRC_Y), ("R4", "1"))
MULTI_VIAS[("R4", "2")] = [(37.2, 79.6), (38.6, 79.6), (40.0, 79.6)]
P("TP3", QX + 1.6, 75.6, 0)
W(W_SIG, (QX + 2.54, SRC_Y), (QX + 2.54, 75.6), ("TP3", "1"))
TP_LABEL["TP3"] = (0.0, 2.0, "center")
GQ_X = QX - 2.54                               # the gate's pin, straight down
P("R6", QX, SRC_Y, 0)                          # 100k gate to source
W(W_SIG, ("Q1", "1"), (GQ_X, SRC_Y), ("R6", "1"))
W(W_SIG, ("R6", "2"), (QX + 2.54, SRC_Y))
P("R5", GQ_X, 75.0, 90)                        # 47 ohm into the gate: pad 2 up to it
FIELD_AT["R5"] = ((-1.7, -0.7, "right"), (-1.7, 0.7, "right"))
W(W_SIG, (GQ_X, SRC_Y), ("R5", "2"))
SOLID_PADS += [("Q1", "2"), ("Q1", "3"), ("R4", "1"), ("D7", "1"), ("D7", "2")]

# ========================================== the relay's coil and its driver ==
COILM_Y = KY + 9.0
W(W_SIG, ("K1", "12"), (KX, COILM_Y), (65.5, COILM_Y))
P("D8", 54.5, COILM_Y + 2.4, 90)               # freewheel: anode up on the coil's -, cathode to +15 V
FIELD_AT["D8"] = ((-2.9, 1.1, "center", 90), (-1.8, 1.1, "center", 90))
VIA_AT[("D8", "1")] = DOWN
W(W_SIG, (54.5, COILM_Y), ("D8", "2"))
P("Q2", 60.0, COILM_Y + 9.0, 90)               # the driver: collector up to the coil's -
FIELD_AT["Q2"] = ((0.0, 8.8, "center"), (0.0, 10.0, "center"))
W(W_SIG, (60.0, COILM_Y), ("Q2", "3"))
P("LED4", 65.5, COILM_Y + 2.5, 270)            # red, POLARIZING: cathode up on the coil's -
W(W_SIG, (65.5, COILM_Y), ("LED4", "1"))
P("R10", 65.5, COILM_Y + 6.5, 90)
W(W_SIG, ("LED4", "2"), ("R10", "2"))
RLY_X = 51.0
P("R8", RLY_X, COILM_Y + 12.5, 90)             # the base resistor; RELAY up from below
W(W_SIG, ("R8", "2"), (RLY_X, COILM_Y + 9.0), ("Q2", "1"))

# ============================================================== the TANK =====
TP_Y = 38.0                                    # TANK+ along the top of the tank
TN_X = 71.0                                    # TANK- down this column ...
TN_Y = 79.0                                    # ... and along the bottom
TANK_END = 113.0
W(W_SIG, ("K1", "3"), (KX - 5.08, TP_Y), (TANK_END, TP_Y))
W(W_SIG, ("K1", "10"), (KX - 5.08, CHAN), (TN_X, CHAN), (TN_X, TN_Y), (TANK_END, TN_Y))
P("D9", TN_X, 41.8, 90)
FIELD_AT["D9"] = ((2.8, -0.7, "left"), (2.8, 0.7, "left"))                        # the tank's clamp, SMBJ12CA, TANK+ to TANK-
W(W_SIG, (TN_X, TP_Y), ("D9", "2"))
W(W_SIG, ("D9", "1"), (TN_X, CHAN))
DIPX, DIPY = 93.0, 46.0
P("SW1", DIPX, DIPY, 0)                        # pads 16..9 along the top (TANK+), 1..8 along the bottom
for k in range(1, 9):
    W(W_SIG, ("SW1", str(17 - k)), (DIPX - 8.89 + 2.54 * (k - 1), TP_Y))
# each switch's capacitance, a column under it: its rail on the left, TANK- on
# the right, the capacitors across as rungs; 3.3 nF, then doubling
BANK = [["3.3nF"], ["6.8nF"], ["10nF", "3.3nF"], ["10nF", "10nF", "6.8nF"],
        ["47nF", "6.8nF"], ["100nF_C0G", "6.8nF"], ["100nF_C0G", "100nF_C0G", "10nF"],
        ["100nF_C0G", "100nF_C0G", "100nF_C0G", "100nF_C0G", "10nF", "10nF"]]
COL_PITCH, HALF = 5.0, 1.48                    # the rails 2.96 apart: a 1206's pads; an 0805 sits between
COL0 = DIPX + 1.27 + HALF - 4 * COL_PITCH      # column 5's rail straight under its pad
LEVEL0, LY0, RUNG = 53.6, 60.5, 3.0
COLS = []
cref = 10
for k, caps in enumerate(BANK):
    cx = COL0 + COL_PITCH * k
    left, right = cx - HALF, cx + HALF
    px = DIPX - 8.89 + 2.54 * k
    level = LEVEL0 + (k if left < px else 7 - k) * 1.0      # the outer columns turn nearest the DIP
    last = LY0 + RUNG * (len(caps) - 1)
    W(W_SIG, ("SW1", str(k + 1)), (px, level), (left, level), (left, last))
    W(W_SIG, (f"C{cref}", "2"), (right, LY0), (right, TN_Y))
    for i, c in enumerate(caps):
        ref = f"C{cref}"
        cref += 1
        y = LY0 + RUNG * i
        P(ref, cx, y, 0)
        if parts.PASSIVES[c].get("footprint", "C_0805") == "C_0805":
            W(W_SIG, (left, y), (ref, "1"))
            if i:
                W(W_SIG, (ref, "2"), (right, y))
        hide(ref)
    COLS.append((cx, last))
assert cref == 30
P("TP5", 108.5, TP_Y - 3.6, 0)
W(W_SIG, (108.5, TP_Y), ("TP5", "1"))
P("TP6", TANK_END, TN_Y + 4.6, 0)
W(W_SIG, (TANK_END, TN_Y), ("TP6", "1"))
# CAL IN from the top edge: 51 ohm across the jack, 1M down into TANK+
P("J4", 62.0, BNC_IN, 90)
P("R13", 65.5, 14.0, 0)
VIA_AT[("R13", "2")] = RIGHT
W(W_SIG, ("J4", "1"), (62.0, 14.0), ("R13", "1"))
P("R14", 62.0, 26.0, 270)
W(W_SIG, (62.0, 14.0), ("R14", "1"))
W(W_SIG, ("R14", "2"), (62.0, TP_Y))

# ====================================================== the PREAMPLIFIER =====
UAX = 130.0                                    # U1 over U2
U1Y, U2Y = TP_Y + OA_IN, TN_Y + OA_IN
opamp("U1", UAX, U1Y)
opamp("U2", UAX, U2Y)
bypass("C80", "C81", UAX, U1Y)
bypass("C82", "C83", UAX, U2Y)
P("R15", 116.0, TP_Y, 0)                       # 1k into each input
W(W_SIG, (TANK_END, TP_Y), ("R15", "1"))
W(W_SIG, ("R15", "2"), ("U1", "3"))
P("R11", 119.5, TP_Y - 2.9, 270)               # 1M from U1's + to ground: pad 2 down on it
W(W_SIG, (119.5, TP_Y), ("R11", "2"))
P("R16", 116.0, TN_Y, 0)
W(W_SIG, (TANK_END, TN_Y), ("R16", "1"))
GSX = 122.0                                    # the gain-setting column, down the - inputs
W(W_SIG, ("R16", "2"), (GSX - 1.5, TN_Y), (GSX + 1.5, TN_Y), ("U2", "3"))
HOPS.append(((GSX - 1.5, TN_Y), (GSX + 1.5, TN_Y)))        # U2's + dives under the column
P("R12", 118.8, TN_Y - 2.9, 90)                # 1M from U2's + to ground: pad 1 down on it
FIELD_AT["R12"] = ((0.0, -6.8, "center"), (0.0, -5.6, "center"))
W(W_SIG, (118.8, TN_Y), ("R12", "1"))
FB1_Y, FB2_Y = U1Y + 8.0, U2Y + 8.0
OXA = UAX + OA_W / 2 + 1.5
P("R17", UAX - 1.0, FB1_Y, 0)
P("R18", UAX - 1.0, FB2_Y, 0)
for r in ("R17", "R18"):
    FIELD_AT[r] = ((0.0, 1.75, "center"), (0.0, 2.95, "center"))
P("R19", GSX, (U1Y + U2Y) / 2, 270)            # Rg, 200 ohm: pad 1 up to U1's -
W(W_SIG, ("U1", "4"), (GSX, U1Y + OA_IN), (GSX, FB1_Y), ("R17", "1"))
W(W_SIG, (GSX, FB1_Y), ("R19", "1"))
W(W_SIG, ("R19", "2"), (GSX, U2Y + OA_IN), ("U2", "4"))
W(W_SIG, (GSX, U2Y + OA_IN), (GSX, FB2_Y), ("R18", "1"))
W(W_SIG, ("U1", "1"), (OXA, U1Y), (OXA, FB1_Y), ("R17", "2"))
W(W_SIG, ("U2", "1"), (OXA, U2Y), (OXA, FB2_Y), ("R18", "2"))
INA_X = OXA + 4.5                              # INA A and INA B down and up to U3
P("TP7", OXA + 2.2, U1Y - 3.8, 0)
W(W_SIG, (OXA, U1Y), (OXA + 2.2, U1Y), ("TP7", "1"))
P("TP8", OXA + 2.2, U2Y + 3.8, 0)
W(W_SIG, (OXA, U2Y), (OXA + 2.2, U2Y), ("TP8", "1"))
# U3, the difference amplifier, between them
U3X, U3Y = INA_X + 14.0, (U1Y + U2Y) / 2
opamp("U3", U3X, U3Y)
bypass("C84", "C85", U3X, U3Y)
XL3 = U3X - OA_W / 2
P("R21", XL3 - 5.0, U3Y - OA_IN, 0)
P("R20", XL3 - 5.0, U3Y + OA_IN, 0)
W(W_SIG, (OXA + 2.2, U1Y), (INA_X, U1Y), (INA_X, U3Y - OA_IN), ("R21", "1"))
W(W_SIG, (OXA + 2.2, U2Y), (INA_X, U2Y), (INA_X, U3Y + OA_IN), ("R20", "1"))
W(W_SIG, ("R21", "2"), ("U3", "3"))
W(W_SIG, ("R20", "2"), ("U3", "4"))
P("R22", XL3 - 1.8, U3Y - OA_IN - 2.9, 270)    # U3's + to ground: pad 2 down on it
FIELD_AT["R22"] = ((0.0, -6.4, "center"), (0.0, -5.2, "center"))
W(W_SIG, (XL3 - 1.8, U3Y - OA_IN), ("R22", "2"))
FB3_Y = U3Y + 9.0
OX3 = U3X + OA_W / 2 + 1.5
P("R23", U3X, FB3_Y, 0)
W(W_SIG, (XL3 - 1.8, U3Y + OA_IN), (XL3 - 1.8, FB3_Y), ("R23", "1"))
W(W_SIG, ("U3", "1"), (OX3, U3Y), (OX3, FB3_Y), ("R23", "2"))

# =========================================================== the FILTERS =====
ROW = U3Y                                      # the signal row: every stage's + input on it
P("TP9", OX3 + 3.2, ROW + 3.6, 0)
TP_LABEL["TP9"] = (0.0, 2.0, "center")
W(W_SIG, (OX3, ROW), (OX3 + 3.2, ROW), ("TP9", "1"))


def sallen_key(u, sa, sb, fb, sh, cx, in_x, cp, cm, tp):
    """A unity-gain Sallen-Key stage with its + input on the signal row: the two
    series parts along the row, the feedback part over the top from their node
    to the output column, the shunt from + down to ground, - tied to the output
    under the triangle; the output column carries the signal on along the row.
    Returns the output column's x."""
    cy = ROW + OA_IN
    opamp(u, cx, cy)
    bypass(cp, cm, cx, cy)
    xl = cx - OA_W / 2
    xa, xb = xl - 8.4, xl - 4.4
    P(sa, xa, ROW, 0)
    P(sb, xb, ROW, 0)
    W(W_SIG, (in_x, ROW), (sa, "1"))
    W(W_SIG, (sa, "2"), (sb, "1"))
    W(W_SIG, (sb, "2"), (u, "3"))
    sx = xl - 1.4
    P(sh, sx, ROW + 2.3, 270)                     # pad 1 up on the + input, pad 2 down to ground
    W(W_SIG, (sx, ROW), (sh, "1"))
    VIA_AT[(sh, "2")] = LEFT
    FIELD_AT[sh] = ((-1.6, 3.1, "center"), (-1.6, 4.3, "center"))
    node = (xa + xb) / 2
    fy = ROW - 6.0
    P(fb, cx - 2.0, fy, 0)
    ox = cx + OA_W / 2 + 1.5
    W(W_SIG, (node, ROW), (node, fy), (fb, "1"))
    W(W_SIG, (u, "1"), (ox, cy), (ox, fy), (fb, "2"))
    W(W_SIG, (u, "4"), (xl - 0.8, cy + OA_IN), (xl - 0.8, cy + 7.5), (ox, cy + 7.5), (ox, cy))
    P(tp, ox + 2.6, ROW - 3.6, 0)
    W(W_SIG, (ox, ROW), (ox + 2.6, ROW), (tp, "1"))
    TP_LABEL[tp] = (0.0, -2.0, "center")
    return ox


STAGE = 18.0                                   # from one stage's output column to the next one's middle
FIELD_AT["C30"] = ((0.0, -1.75, "center"), (0.7, 1.75, "center"))
o4 = sallen_key("U4", "C30", "C31", "R24", "R25", OX3 + STAGE, OX3 + 3.2, "C86", "C87", "TP10")
o5 = sallen_key("U5", "C32", "C33", "R26", "R27", o4 + STAGE, o4 + 2.6, "C88", "C89", "TP11")
o6 = sallen_key("U6", "R28", "R29", "C34", "C35", o5 + STAGE, o5 + 2.6, "C90", "C91", "TP12")

# ========================================================= the GAIN stage =====
# down from the low-pass's output past the end of the row, back under it to U7
GROW = 95.0                                    # U7's + input
DROPX = o6 + 2.6
U7X, U7Y = 205.0, GROW + OA_IN
opamp("U7", U7X, U7Y)
bypass("C92", "C93", U7X, U7Y)
XL7 = U7X - OA_W / 2
W(W_SIG, (DROPX, ROW), (DROPX, GROW - 6.0), (XL7 - 3.0, GROW - 6.0), (XL7 - 3.0, GROW), ("U7", "3"))
OX7 = U7X + OA_W / 2 + 1.5
FB7_Y = U7Y + 7.5
MX7 = XL7 - 0.8                                # the - node's column
P("R30", U7X, FB7_Y, 0)
FIELD_AT["R30"] = ((0.0, 1.75, "center"), (0.0, 2.95, "center"))
W(W_SIG, ("U7", "4"), (MX7, U7Y + OA_IN), (MX7, FB7_Y), ("R30", "1"))
W(W_SIG, ("U7", "1"), (OX7, U7Y), (OX7, FB7_Y), ("R30", "2"))
SWX = MX7 - 0.75                               # SW2's common (pin 2, +0.75) under the column
SW2_PINS = FB7_Y + 5.0
P("SW2", SWX, SW2_PINS + 1.95, 0)
W(W_SIG, (MX7, FB7_Y), ("SW2", "2"))
P("R31", SWX - 2.25 - 5.0, SW2_PINS, 0)        # 10k (x21) left of pin 1: pad 2 on it, pad 1 to ground
VIA_AT[("R31", "1")] = LEFT
FIELD_AT["R31"] = ((0.0, 1.75, "center"), (0.0, 2.95, "center"))
W(W_SIG, ("R31", "2"), ("SW2", "1"))
P("R32", SWX + 2.25 + 5.0, SW2_PINS, 180)      # 1k (x201) right of pin 3
VIA_AT[("R32", "1")] = RIGHT
FIELD_AT["R32"] = ((0.0, 1.75, "center"), (0.0, 2.95, "center"))
hide("SW1", "SW2", "SW3", "SW4", "J1", "J4", "J5", "J7", "J8")
W(W_SIG, ("R32", "2"), ("SW2", "3"))
P("TP13", OX7 + 2.6, U7Y - 3.6, 0)
W(W_SIG, (OX7, U7Y), (OX7 + 2.6, U7Y), ("TP13", "1"))
P("R33", OX7 + 6.0, U7Y, 0)
W(W_SIG, (OX7 + 2.6, U7Y), ("R33", "1"))
BOARD_W = round(DROPX + 5.4, 1)
J5X = BOARD_W - BNC_IN
P("J5", J5X, U7Y, 0)                           # OUT, the barrel off the right edge
W(W_SIG, ("R33", "2"), ("J5", "1"))

# =========================================================== the SEQUENCER ===
LINK_Y = 91.0                                  # GATE and RELAY come up from the sequencer along here
VTH_Y = 99.0                                   # the threshold the two delays compare with
CMP_Y = 108.0                                  # the two comparators
BUS_Y = 121.0                                  # POL CMD, from the switches to the delays and SYNC
# the threshold divider, at the left
P("R51", 12.0, VTH_Y - 2.9, 270)
W(W_SIG, (12.0, VTH_Y), ("R51", "2"))
P("R52", 12.0, VTH_Y + 2.9, 270)
W(W_SIG, (12.0, VTH_Y), ("R52", "1"))
P("C54", 18.0, VTH_Y + 2.9, 270)
W(W_SIG, (18.0, VTH_Y), ("C54", "1"))


def delay(u, r, dio, dio_rot, c, tp, cx, out_x, out_ref):
    """One delay: R from POL CMD up to the comparator's + input, its diode
    beside it, the capacitor down from the node to ground; the threshold into
    the - input from the bus above; the output up to LINK_Y and along it to
    where it is going.  Returns the output column's x."""
    opamp(u, cx, CMP_Y)
    xl = cx - OA_W / 2
    yp = CMP_Y + OA_IN
    rx, dx_, cxx = xl - 20.0, xl - 14.0, xl - 2.6
    P(r, rx, BUS_Y - 4.5, 90)                      # pad 1 down on POL CMD, pad 2 up on the node
    FIELD_AT[r] = ((-1.7, -0.7, "right"), (-1.7, 0.7, "right"))
    W(W_SIG, (rx, BUS_Y), (r, "1"))
    W(W_SIG, (r, "2"), (rx, yp), (u, "4"))
    P(dio, dx_, BUS_Y - 4.0, dio_rot)
    lo, hi = ("1", "2") if dio_rot == 90 else ("2", "1")
    W(W_SIG, (dx_, BUS_Y), (dio, lo))
    W(W_SIG, (dio, hi), (dx_, yp))
    P(c, cxx, yp + 3.2, 270)                       # pad 1 up on the node
    W(W_SIG, (cxx, yp), (c, "1"))
    FIELD_AT[c] = ((-1.6, -0.7, "right"), (-1.6, 0.7, "right"))
    P(tp, xl - 9.5, yp - 3.8, 0)
    W(W_SIG, (xl - 9.5, yp), (tp, "1"))
    W(W_SIG, (xl - 1.5, VTH_Y), (xl - 1.5, CMP_Y - OA_IN), (u, "3"))
    ox = cx + OA_W / 2 + 1.5
    W(W_SIG, (u, "1"), (ox, CMP_Y), (ox, LINK_Y), (out_x, LINK_Y), out_ref)
    return ox


U9X, U10X = 42.0, 76.0
gx = delay("U9", "R49", "D13", 90, "C55", "TP15", U9X, GQ_X, ("R5", "1"))
rx = delay("U10", "R50", "D14", 270, "C56", "TP16", U10X, RLY_X, ("R8", "1"))
W(W_SIG, ("R52", "1"), (12.0, VTH_Y), (U10X - OA_W / 2 - 1.5, VTH_Y))
bypass("C96", None, U9X, CMP_Y)
bypass("C97", None, U10X, CMP_Y)
# GATE dives under the coil's loop and under the threshold bus
HOPS.append(((GQ_X, YB - 1.6), (GQ_X, YB + 1.6)))
HOPS.append(((gx, VTH_Y - 1.6), (gx, VTH_Y + 1.6)))
# the gate's pull-up and probe on its column; the relay line's likewise
P("R7", gx + 2.4, LINK_Y + 3.0, 180)            # pad 2 left on GATE, pad 1 to +15 V
VIA_AT[("R7", "1")] = RIGHT
W(W_SIG, (gx, LINK_Y + 3.0), ("R7", "2"))
P("TP4", gx - 3.0, LINK_Y + 3.4, 0)
TP_LABEL["TP4"] = (-2.6, 0.0, "right")
W(W_SIG, (gx, LINK_Y + 3.4), ("TP4", "1"))
P("R9", rx + 2.4, LINK_Y + 3.0, 180)
VIA_AT[("R9", "1")] = RIGHT
W(W_SIG, (rx, LINK_Y + 3.0), ("R9", "2"))
P("TP17", rx + 3.2, LINK_Y + 7.4, 0)
W(W_SIG, (rx, LINK_Y + 7.4), ("TP17", "1"))

# --- the switches: SW4 (MODE) over SW3 (SEQUENCE); POL CMD leaves SW4 to the left
X3 = 120.0
P4 = BUS_Y - 3.0                               # SW4's pins
P("SW4", X3 - 1.5, P4 - 1.95, 180)             # pins along the bottom: 1 right, 2, 3 left
SW3_PINS = P4 + 4.5
P("SW3", X3, SW3_PINS + 1.95, 0)               # pins along the top: 1 (EXT) left, 2, 3 (INT) right
W(W_SIG, ("SW3", "2"), ("SW4", "1"))
W(W_SIG, ("SW4", "2"), (X3 - 2.25, BUS_Y), (14.0, BUS_Y))
VIA_AT[("SW4", "3")] = (X3 - 1.5 - 3.5, P4 + 0.45)
P("R42", X3 - 9.0, BUS_Y + 3.0, 270)           # POL CMD's pull-down: pad 1 up on it
FIELD_AT["R42"] = ((-1.7, -0.7, "right"), (-1.7, 0.7, "right"))
W(W_SIG, (X3 - 9.0, BUS_Y), ("R42", "1"))
P("TP14", X3 - 14.0, BUS_Y - 3.6, 0)
TP_LABEL["TP14"] = (0.0, -2.0, "center")
W(W_SIG, (X3 - 14.0, BUS_Y), ("TP14", "1"))

# --- SYNC OUT, a follower of POL CMD to the bottom edge
P("R53", 14.0, BUS_Y + 5.0, 270)
W(W_SIG, (14.0, BUS_Y), ("R53", "1"))
P("Q3", 22.0, BUS_Y + 12.0, 90)
FIELD_AT["Q3"] = ((4.6, -0.7, "left"), (4.6, 0.7, "left"))
W(W_SIG, ("R53", "2"), (14.0, BUS_Y + 12.0), ("Q3", "1"))
EDGE_Y = BOARD_H - BNC_IN                      # the bottom edge's BNCs
P("R55", 30.0, EDGE_Y, 0)
W(W_SIG, ("Q3", "2"), (22.0, EDGE_Y), ("R55", "1"))
P("R54", 19.0, EDGE_Y - 1.6, 180)              # pad 1 right on the emitter line
VIA_AT[("R54", "2")] = LEFT
W(W_SIG, (22.0, EDGE_Y - 1.6), ("R54", "1"))
P("J8", 40.0, EDGE_Y, 270)
W(W_SIG, ("R55", "2"), ("J8", "1"))

# --- POLARIZE IN: a comparator at 1.4 V with hysteresis, from the bottom edge
U8X, U8Y = 98.0, 133.0
XL8 = U8X - OA_W / 2
J7X = 66.0
P("J7", J7X, EDGE_Y, 270)
opamp("U8", U8X, U8Y)
bypass("C95", None, U8X, U8Y)
P("R43", J7X - 2.5, U8Y + 4.0, 180)            # 100k across the jack: pad 1 on its line
W(W_SIG, (J7X, U8Y + 4.0), ("R43", "1"))
VIA_AT[("R43", "2")] = LEFT
FIELD_AT["R43"] = ((0.0, -2.95, "center"), (0.0, -1.75, "center"))
P("R44", 78.0, U8Y + OA_IN, 0)
W(W_SIG, ("J7", "1"), (J7X, U8Y + OA_IN), ("R44", "1"))
P("R59", 89.0, U8Y + OA_IN, 0)                 # 10k between the clamped node and the comparator's pin
W(W_SIG, ("R44", "2"), ("R59", "1"))
W(W_SIG, ("R59", "2"), ("U8", "4"))
P("D12", 84.5, U8Y + OA_IN + 2.4, 90)          # the BAT54S: common up on the clamped node
FIELD_AT["D12"] = ((-1.9, -0.6, "right"), (-1.9, 0.6, "right"))
W(W_SIG, (84.5, U8Y + OA_IN), ("D12", "3"))
VIA_AT[("D12", "1")] = DOWN
VIA_AT[("D12", "2")] = DOWN
NODE8_Y = U8Y - OA_IN
P("R45", XL8 - 9.0, NODE8_Y - 2.9, 270)        # +15 V on top, pad 2 down on the node
P("R46", XL8 - 5.0, NODE8_Y - 2.9, 90)         # pad 1 down on the node, ground on top
FIELD_AT["R45"] = ((-1.7, -0.7, "right"), (-1.7, 0.7, "right"))
W(W_SIG, (XL8 - 9.0, NODE8_Y), ("U8", "3"))
W(W_SIG, ("R45", "2"), (XL8 - 9.0, NODE8_Y))
W(W_SIG, ("R46", "1"), (XL8 - 5.0, NODE8_Y))
OX8 = U8X + OA_W / 2 + 1.5
P("R47", U8X - 1.0, U8Y + 9.0, 0)              # the hysteresis, from the output back to +
W(W_SIG, (87.0, U8Y + OA_IN), (87.0, U8Y + 9.0), ("R47", "1"))   # the hysteresis taps the clamped node, before R59
W(W_SIG, ("U8", "1"), (OX8, U8Y), (OX8, U8Y + 9.0), ("R47", "2"))
EXT_X = X3 - 2.25 - 3.0
W(W_SIG, (OX8, U8Y), (EXT_X, U8Y), (EXT_X, SW3_PINS), ("SW3", "1"))
P("R48", OX8 + 4.0, U8Y - 2.9, 270)            # the pull-up: pad 2 down on the output
W(W_SIG, (OX8 + 4.0, U8Y), ("R48", "2"))
P("TP19", OX8 + 4.5, U8Y + 3.6, 0)
W(W_SIG, (OX8 + 4.5, U8Y), ("TP19", "1"))

# --- the TIMER, right of the switches
UTX, UTY = X3 + 16.0, SW3_PINS - 0.64          # the 555: its OUT (pin 3) level with SW3's pins
P("U11", UTX, UTY, 0)
W(W_SIG, ("U11", "3"), ("SW3", "3"))
W(W_SIG, ("U11", "2"), (UTX, UTY - 0.64), (UTX, UTY + 0.64), ("U11", "6"))   # TRIG to THR, under the body
DIS_Y, CAP_Y = UTY - 9.0, UTY + 9.0
TX0 = UTX + 6.0
TX1 = TX0 + 33.0
W(W_SIG, ("U11", "7"), (TX0, UTY - 0.64), (TX0, DIS_Y), (TX0 + 28.0, DIS_Y))
W(W_SIG, ("U11", "6"), (TX0 + 1.5, UTY + 0.64), (TX0 + 1.5, CAP_Y), (TX1, CAP_Y))
P("C53", UTX + 4.0, UTY + 4.6, 90)             # CONT's 10 nF: pad 2 up from pin 5
W(W_SIG, ("U11", "5"), (UTX + 4.0, UTY + 1.91), ("C53", "2"))
VIA_AT[("C53", "1")] = DOWN
FIELD_AT["C53"] = ((-1.6, -0.7, "right"), (-1.6, 0.7, "right"))
VIA_AT[("U11", "4")] = LEFT
VIA_AT[("U11", "1")] = LEFT
VIA_AT[("U11", "8")] = UP
FIELD_AT["U11"] = ((-4.5, -5.6, "right"), (-4.5, -4.4, "right"))
P("D10", TX0 + 4.5, UTY, 90)                    # charge: anode up on DIS, cathode down on the capacitor
W(W_SIG, (TX0 + 4.5, DIS_Y), ("D10", "2"))
W(W_SIG, ("D10", "1"), (TX0 + 4.5, CAP_Y))
RVX = TX0 + 17.0
P("RV2", RVX, DIS_Y + 6.1, 180)                 # LISTEN TIME: 1 up to DIS, the wiper down to R41
FIELD_AT["RV2"] = ((4.2, -2.0, "left"), (4.2, -0.8, "left"))
W(W_SIG, ("RV2", "1"), (RVX + 2.54, DIS_Y))
P("R41", RVX, DIS_Y + 10.9, 270)
W(W_SIG, ("RV2", "2"), ("R41", "1"))
W(W_SIG, ("RV2", "3"), (RVX - 2.54, DIS_Y + 8.2), (RVX, DIS_Y + 8.2))
P("D11", RVX, DIS_Y + 15.3, 270)                # discharge: anode down on the capacitor
W(W_SIG, ("R41", "2"), ("D11", "1"))
W(W_SIG, ("D11", "2"), (RVX, CAP_Y))
RV1X = TX0 + 28.0
P("RV1", RV1X, DIS_Y - 3.5, 180)                # POLARIZE TIME: the wiper and 3 down on DIS
FIELD_AT["RV1"] = ((4.2, -2.0, "left"), (4.2, -0.8, "left"))
W(W_SIG, ("RV1", "2"), (RV1X, DIS_Y))
W(W_SIG, ("RV1", "3"), (RV1X - 2.54, DIS_Y))
P("R40", RV1X + 2.54, DIS_Y - 11.0, 270)        # from +15 V down to RV1's 1
W(W_SIG, ("RV1", "1"), ("R40", "2"))
for i, x in enumerate((TX0 + 8.0, TX0 + 18.0, TX0 + 28.0)):
    P(f"C{50 + i}", x, CAP_Y + 4.5, 270)        # pad 1 up on the capacitor line, pad 2 to ground
    W(W_SIG, (x, CAP_Y), (f"C{50 + i}", "1"))
    MARKS.append(("gnd", f"C{50 + i}", "2", 0, 1, 0.8))
    FIELD_AT[f"C{50 + i}"] = ((3.8, -0.7, "left"), (3.8, 0.7, "left"))
P("TP18", TX1 + 1.0, CAP_Y - 3.6, 0)
W(W_SIG, (TX1, CAP_Y), (TX1 + 1.0, CAP_Y), ("TP18", "1"))
P("C94", UTX - 1.0, UTY - 4.6, 0)
VIA_AT[("C94", "1")] = UP
VIA_AT[("C94", "2")] = UP
hide("C94")

# ================================================================ HEADPHONES ==
# OUT down from TP13's hook, through R58 onto the VOLUME knob's clockwise end; the
# wiper into U12, a follower; R56 to the tip and R57 to the ring of J9, at the right edge
PH_Y = 124.0                                   # the tap's run along under the GAIN box
RV3X, RV3Y = 200.0, 140.0                      # the knob, by its pin 1: pins 3, 2, 1 down its right side
P("RV3", RV3X, RV3Y, 180)                      # the body (and the shaft) to the left of its pins
FIELD_AT["RV3"] = ((-13.6, -9.6, "left"), (-13.6, -8.4, "left"))
W(W_SIG, (OX7 + 2.6, U7Y), (OX7 + 2.6, PH_Y), (RV3X, PH_Y), ("R58", "1"))
P("R58", RV3X, PH_Y + 3.5, 270)                # 62k: pad 1 up on OUT, pad 2 down to the knob
FIELD_AT["R58"] = ((1.7, -0.7, "left"), (1.7, 0.7, "left"))
W(W_SIG, ("R58", "2"), ("RV3", "3"))
MARKS.append(("gnd", "RV3", "1", 0, 1, 0.7))
U12X, U12Y = RV3X + 10.0, RV3Y - 2.5 + OA_IN  # its + input level with the wiper
opamp("U12", U12X, U12Y)
bypass("C98", "C99", U12X, U12Y)
XL12 = U12X - OA_W / 2
OX12 = U12X + OA_W / 2 + 1.5
W(W_SIG, ("RV3", "2"), ("U12", "3"))
W(W_SIG, ("U12", "4"), (XL12 - 0.8, U12Y + OA_IN), (XL12 - 0.8, U12Y + 7.0), (OX12, U12Y + 7.0), (OX12, U12Y))
W(W_SIG, ("U12", "1"), (OX12, U12Y))
P("TP22", OX12 + 2.6, U12Y - 3.6, 0)
TP_LABEL["TP22"] = (0.0, -2.0, "center")
W(W_SIG, (OX12, U12Y), (OX12 + 2.6, U12Y), ("TP22", "1"))
J9X = BOARD_W - 3.5                            # the sleeve 3.5 mm in from the edge (CUI's drawing)
J9Y = 133.0
P("J9", J9X, J9Y, 90)                          # the plug in from the right edge: T 5 mm in and up, R 5 mm in and down
hide("J9")
SPLIT_X = OX12 + 6.0
W(W_SIG, (OX12 + 2.6, U12Y), (SPLIT_X, U12Y), (SPLIT_X, J9Y - 5.0), ("R56", "1"))
W(W_SIG, (SPLIT_X, J9Y + 5.0), ("R57", "1"))
P("R56", SPLIT_X + 4.5, J9Y - 5.0, 0)          # 100 ohm to the tip (left)
P("R57", SPLIT_X + 4.5, J9Y + 5.0, 0)          # 100 ohm to the ring (right)
MARKS.append(("gnd", "J9", "S", -1, 0))        # the sleeve on the ground plane
T(J9X - 9.3, J9Y - 6.1, "T", 0.8, "center")    # the jack's contacts, named as on a plug, clear of its body
T(J9X - 9.3, J9Y + 6.1, "R", 0.8, "center")
T(J9X - 4.0, J9Y + 7.4, "PHONES", 1.0, "center")   # the jack's name beside it; J9 is in the BOM
W(W_SIG, ("R56", "2"), ("J9", "T"))
W(W_SIG, ("R57", "2"), ("J9", "R"))

# ===================================================================== POWER ==
J1X = BOARD_W - 42.0
P("J1", J1X, 4.3, 0)                           # +15 V, ground, -15 V from the top edge
MARKS.append(("gnd", "J1", "2", 0, 1))
T(J1X - 9.0, 6.0, "+15", 0.8, "right")         # each outer screw's rail beside it; the middle one's ground mark
T(J1X + 9.0, 6.0, "-15", 0.8, "left")
P("D1", J1X - 5.0, 12.5, 90)                   # anode up to J1.1, cathode down to +15 V
W(0.6, ("J1", "1"), ("D1", "2"))
P("D2", J1X + 5.0, 12.5, 270)                  # cathode up to J1.3, anode down to -15 V
W(0.6, ("J1", "3"), ("D2", "1"))
VIA_AT[("D1", "1")] = DOWN
VIA_AT[("D2", "2")] = DOWN
FIELD_AT["D1"] = ((-2.3, -0.7, "right"), (-2.3, 0.7, "right"))
FIELD_AT["D2"] = ((2.3, -0.7, "left"), (2.3, 0.7, "left"))
# each rail's shunts in a row: the rail's flag on top, the part, its ground below, its name under that
PY = 24.0
SHUNTS = [("TP20", J1X - 11.0, 0), ("C3", J1X - 17.0, 270), ("C1", J1X - 24.0, 270), ("D3", J1X - 31.0, 270),
          ("TP21", J1X + 11.0, 0), ("C4", J1X + 16.0, 90), ("C2", J1X + 22.0, 90), ("D4", J1X + 28.5, 90)]
for ref, x, rot in SHUNTS:
    if ref.startswith("TP"):
        P(ref, x, PY - 3.0, 0)
        VIA_AT[(ref, "1")] = UP
        TP_LABEL[ref] = (0.0, 2.0, "center")
        continue
    P(ref, x, PY, rot)
    top = "1" if rot == 270 else "2"
    VIA_AT[(ref, top)] = UP
    VIA_AT[(ref, "2" if top == "1" else "1")] = DOWN
    FIELD_AT[ref] = ((0.0, 8.4, "center"), (0.0, 9.6, "center"))
P("R1", J1X - 37.0, PY - 2.0, 270)             # the +15 V lamp: R1 from the rail, LED1 to ground
P("LED1", J1X - 37.0, PY + 2.0, 90)
W(W_SIG, ("R1", "2"), ("LED1", "2"))
P("R2", J1X + 33.5, PY - 2.0, 90)              # the -15 V lamp: LED2 from ground, R2 to the rail
P("LED2", J1X + 33.5, PY + 2.0, 270)
W(W_SIG, ("LED2", "1"), ("R2", "1"))
VIA_AT[("R1", "1")] = UP
VIA_AT[("LED1", "1")] = DOWN
VIA_AT[("R2", "2")] = UP
VIA_AT[("LED2", "2")] = DOWN
for r in ("R1", "LED1"):
    FIELD_AT[r] = ((-1.7, -0.7, "right"), (-1.7, 0.7, "right"))
for r in ("R2", "LED2"):
    FIELD_AT[r] = ((1.7, -0.7, "left"), (1.7, 0.7, "left"))

# ================================================ probe grounds, holes, marks
GROUND_LOOPS = [("TP100", 112.0, 90.0), ("TP101", 175.0, 80.0), ("TP102", 222.0, 80.0), ("TP103", 233.0, 116.0)]
for (ref, x, y) in GROUND_LOOPS:
    P(ref, x, y, 0)
P("MH1", 4.0, 4.0)
P("MH2", BOARD_W - 4.0, BOARD_H - 4.0)
P("MH3", 4.0, BOARD_H - 4.0)
P("MH4", BOARD_W - 4.0, 4.0)

# ============================================================ the words ======
STORY_CHARS = 112                              # the story's lines, to fit 165-242 mm
c, site, bank = D["coil"], D["site"], D["bank"]
f_L, C_res = site["f_L"], c["C_res"]


def lines(x, y, rows, size=0.8, pitch=1.45, title=None, tsize=1.2):
    """A title and the lines under it, left-justified from (x, y)."""
    if title:
        T(x, y, title, tsize, "left", thick=0.22)
        y += tsize * 0.9 + 0.9
    for i, r in enumerate(rows):
        T(x, y + pitch * i, r, size)


T(103.0, 4.2, parts.BOARD_NAME.upper(), 2.5, "left", thick=0.4)
T(103.0, 7.6, "a proton precession magnetometer for a bottle of water", 0.9)
T(103.0, 9.2, f"rev {parts.REV}, {parts.BOARD_DATE}    {parts.PROJECT_URL}", 0.9)
step_df = f_L * bank["step"] / (2 * C_res)
f_min = 1 / (2 * math.pi * math.sqrt(c["L"] * bank["C_max"]))
on = [str(i + 1) for i in range(8) if c["dip_code"] >> i & 1]
story = (f"1 POLARIZE: the timer closes K1 and turns Q1 on; {c['I_pol']:.1f} A from {c['V_pol']:.0f} V through the coil "
         f"makes {c['B_p'] * 1e3:.1f} mT, {c['B_p'] / (site['F_nT'] * 1e-9):.0f} times Earth's field, and lines up the "
         f"protons in the litre of water inside it.  2 SWITCH OFF: Q1 opens, D7 holds the drain near "
         f"{D['switch_off']['v_clamp_3A']:.0f} V, and the coil's {c['energy'] * 1e3:.0f} mJ is gone in "
         f"{D['switch_off']['t_ramp_ref'] * 1e3:.1f} ms, too fast for the protons to follow.  3 LISTEN: K1 drops back, the "
         f"coil is the tank's inductor, and the protons precess about Earth's field at {f_L:.0f} Hz here "
         f"({site['F_nT'] / 1e3:.1f} uT), inducing {c['emf'] * 1e6:.1f} uV that fades over a second or two.  "
         f"PREAMP x{D['ina']['gain']:.0f}, {D['filter_band']['f_lo']:.0f} Hz to {D['filter_band']['f_hi'] / 1e3:.1f} kHz, "
         f"GAIN x{D['gain']['lo']:.0f} or x{D['gain']['hi']:.0f}: about {D['fid_out_hi']:.1f} V at OUT on HIGH.  "
         f"Point the coil east-west, away from steel and mains.")
import textwrap
lines(165.5, 37.0, textwrap.wrap(story, STORY_CHARS), pitch=1.45, title="HOW IT WORKS", tsize=1.0)
lines(2.0, 27.2, [f"{D['pol_supply']['V'][0]:.0f}-{D['pol_supply']['V'][1]:.0f} V, up to {D['pol_supply']['I_max']:.0f} A",
                  "F1 resets; D5 blows it", "if the supply is reversed"], title="POLARIZING SUPPLY", tsize=1.0)
T(10.6, 18.9, "+", 1.0, "center")
T(1.5, 35.4, "COIL", 1.2, "left", thick=0.22)
T(2.0, 37.7, f"{D['switch_off']['v_clamp_3A']:.0f} V at switch-off: do not touch", 0.8)
T(9.0, 35.4, f"{c['N']} turns {c['wire'].split(' (')[0]}, {c['L'] * 1e3:.1f} mH, {c['R']:.1f} ohm", 0.8)
T(8.0, 45.2, "A", 0.9, "center")
T(8.0, 50.3, "B", 0.9, "center")
T(9.4, CHAN - 5.0, "shield", 0.8)
lines(12.0, 65.0, ["Q1 off: the coil's current", f"dies in D7, near {D['switch_off']['v_clamp_3A']:.0f} V,",
                   f"in {D['switch_off']['t_ramp_ref'] * 1e3:.1f} ms; I POL: 0.1 V/A"], title="POLARIZING SWITCH", tsize=1.0)
lines(53.0, 75.6, ["RELAY high: Q2 pulls K1", "in and LED4 lights"], title="RELAY DRIVER", tsize=1.0)
lines(70.5, 19.8, [
    f"the coil ({c['L'] * 1e3:.1f} mH) and SW1's C0G capacitors,",
    f"tuned to the protons: {f_L:.0f} Hz needs {C_res * 1e9:.0f} nF,",
    f"switches {' '.join(on)} ON.  Each switch adds the column",
    f"under it: {bank['step'] * 1e9:.1f} nF steps, {step_df:.0f} Hz near 2 kHz;",
    f"all eight {bank['C_max'] * 1e9:.0f} nF ({f_min:.0f} Hz).  D9 clamps it."], title="TANK")
T(DIPX, 35.6, "SW1  TUNE", 0.9, "center")
T(DIPX + 11.6, DIPY + 3.6, "ON", 0.8)
T(DIPX + 11.6, DIPY - 3.6, "OFF", 0.8)
for k, sw in enumerate(bank["switches"]):
    cx = COL0 + COL_PITCH * k
    T(cx + 0.35, LY0 - 2.2, str(sw["sw"]), 0.8, "center")
    v = sw["C"] * 1e9
    T(cx, TN_Y + 2.0, f"{v:.1f}n" if v < 10 else f"{v:.0f}n", 0.8, "center")
lines(70.0, 3.0, ["a test signal through R14 into the tank:", "1 uA per volt; R13 is a 51 ohm load; 5 Vpp max"],
      title="CAL IN")
lines(141.0, 30.0, [f"U1-U3, x{D['ina']['gain']:.0f} (Rg is R19)"], title="PREAMPLIFIER", tsize=1.0)
lines(166.0, 49.2, [], title=f"HIGH-PASS, -3 dB at {D['filter_band']['f_lo']:.0f} Hz: U4, U5", tsize=1.0)
lines(215.0, 49.2, [], title=f"LOW-PASS, {D['filter_band']['f_hi'] / 1e3:.1f} kHz: U6", tsize=1.0)
lines(186.5, 88.6, [f"x{D['gain']['lo']:.0f} or", f"x{D['gain']['hi']:.0f}"], title="GAIN", tsize=1.0)
T(SWX - 4.6, SW2_PINS + 6.6, "LOW", 0.8, "center")
T(SWX + 5.4, SW2_PINS + 6.6, "HIGH", 0.8, "center")
T(SWX + 0.4, SW2_PINS + 8.2, f"SW2: x{D['gain']['total_lo']:.0f} or x{D['gain']['total_hi']:.0f} in all", 0.8, "center")
lines(229.0, 105.6, ["through 1k"], title="OUT")
T(165.5, 3.0, "POWER", 1.2, "left", thick=0.22)
T(165.5, 5.0, "J1: +15 V, ground, -15 V", 0.8)
lines(2.0, 89.4, [], title="SEQUENCER")
lines(1.8, 106.0, [f"{D['delay']['v_th']:.1f} V,", "R51 R52"], title="THRESHOLD", tsize=0.9)
lines(88.5, 102.0, [f"POL CMD up: RELAY at once, GATE",
                    f"{D['delay']['t_gate'] * 1e3:.0f} ms later (R49, C55); down: GATE",
                    f"off at once, RELAY {D['delay']['t_hold'] * 1e3:.0f} ms later (R50, C56)"], title="DELAY, HOLD", tsize=0.9)
lines(46.0, 140.0, ["POL CMD, high", "while polarizing"], title="SYNC OUT", tsize=0.9)
lines(72.2, 144.2, [f"high (> {D['ext']['v_th']:.1f} V): polarize; open: listen; ±{D['ext']['v_max']:.0f} V max"],
      title="POLARIZE IN", tsize=0.9)
T(X3 - 1.5, P4 - 8.6, "MODE", 0.8, "center")
T(X3 - 5.0, P4 - 7.2, "LISTEN", 0.8, "center")
T(X3 + 1.8, P4 - 7.2, "RUN", 0.8, "center")
T(X3 - 3.5, SW3_PINS + 6.0, "EXT", 0.8, "center")
T(X3 + 4.5, SW3_PINS + 6.0, "TIMER", 0.8, "center")
T(X3 + 0.5, SW3_PINS + 7.5, "SEQUENCE", 0.8, "center")
lines(141.0, 94.5, [f"U11, a 555: POLARIZE TIME (RV1) and",
                    f"LISTEN TIME (RV2), each {D['timer']['t_pol'][0]:.1f} to {D['timer']['t_pol'][1]:.1f} s"], title="TIMER", tsize=0.9)
T(RV1X + 4.2, DIS_Y - 3.5 + 0.4, "POLARIZE", 0.8)
T(RV1X + 4.2, DIS_Y - 3.5 + 1.6, "TIME", 0.8)
T(RV1X - 4.6, DIS_Y - 3.5 - 3.2, "clockwise", 0.8, "right")     # the sense, left of each trimmer's body
T(RV1X - 4.6, DIS_Y - 3.5 - 2.0, "longer", 0.8, "right")
T(RVX - 4.6, DIS_Y + 6.1 - 3.2, "clockwise", 0.8, "right")
T(RVX - 4.6, DIS_Y + 6.1 - 2.0, "longer", 0.8, "right")
T(RVX + 4.2, DIS_Y + 6.1 + 0.4, "LISTEN", 0.8)
T(RVX + 4.2, DIS_Y + 6.1 + 1.6, "TIME", 0.8)
lines(117.0, 134.0, ["U11 NE555: 1 GND, 2 TRIG, 3 OUT, 4 RESET,", "5 CONT, 6 THRESH, 7 DISCH, 8 +15 V"], size=0.8)
lines(2.0, 120.0 - 4.0, [], title=None)
T(120.0, 145.0, "U1-U7, U12 OPA197; U8-U10 TS391; C80-C99", 0.8)
T(120.0, 146.45, "100 nF at each IC's supply pins", 0.8)
ph = D["phones"]
lines(OX7 + 4.0, PH_Y - 0.6, [f"full volume: x{ph['k_max'] * ph['k_ear']:.3f} of OUT into {ph['Z']:.0f} ohm",
                               "T tip, left ear; R ring, right; S sleeve"])
lines(186.5, 123.6, [], title="HEADPHONES", tsize=1.0)
T(RV3X - 13.0, RV3Y + 4.4, "VOLUME", 1.0)       # under the knob's body, not on it
T(RV3X - 13.0, RV3Y + 6.0, "clockwise louder", 0.8)

BOXES += [
    (1.5, 1.5, 40.6, 33.0),                                   # POLARIZING SUPPLY
    (43.0, 1.0, 101.0, 16.5),                                 # CAL IN
    (69.2, 17.5, 114.5, 86.0),                                # TANK
    (114.8, 28.5, 163.0, 95.5),                               # PREAMPLIFIER
    (163.6, 47.0, 213.9, 73.5),                               # HIGH-PASS
    (214.4, 47.0, 241.5, 73.5),                               # LOW-PASS
    (186.0, 86.0, 228.0, 121.5),                              # GAIN
    (228.5, 86.0, 241.5, 110.0),                              # OUT
    (159.0, 1.5, 241.5, 36.0),                                # POWER
    (185.0, 122.2, 241.5, 148.5),                             # HEADPHONES
    ([(1.5, 88.0), (113.0, 88.0), (113.0, 96.5), (184.0, 96.5), (184.0, 148.5), (1.5, 148.5)],),   # SEQUENCER
]

FIDUCIALS = [(10.0, BOARD_H - 14.0), (154.0, 14.0), (BOARD_W - 17.0, BOARD_H - 3.5)]
LAYER_MARK_AT = (166.0, BOARD_H - 5.0)
QR_AT, QR_MODULE = (200.0, 80.0), 0.6
BACK_TITLE_AT = (BOARD_W / 2, 14.0)
BACK_X, BACK_Y, BACK_PITCH, BACK_SIZE = 228.0, 26.0, 1.75, 1.0
GAMMA = 42.577                                  # Hz per uT, the proton's gyromagnetic ratio over 2 pi
BACK_TEXT = [
    "USING IT  (docs/HANDBOOK.md has the whole story)",
    f"1  Wind the coil: {c['N']} turns of {c['wire'].split(' (')[0]} in {c['layers']} layers on a {c['former_od'] * 1e3:.0f} mm former, "
    f"{c['length'] * 1e3:.0f} mm long ({c['L'] * 1e3:.1f} mH, {c['R']:.1f} ohm); fill it with {c['sample_litres']:.0f} litre of water.",
    f"2  Power: +15 V and -15 V at J1; {D['pol_supply']['V'][0]:.0f}-{D['pol_supply']['V'][1]:.0f} V, up to "
    f"{D['pol_supply']['I_max']:.0f} A, at POLARIZE SUPPLY (a battery is the quietest).",
    f"3  Tune SW1 to the protons where you are: f = {GAMMA} Hz/uT x B.  Claremont, {site['F_nT'] / 1e3:.1f} uT: {f_L:.0f} Hz, "
    f"switches {' '.join(on)} ON.",
    f"   Earth's field runs {D['world']['F_nT'][0] / 1e3:.0f}-{D['world']['F_nT'][1] / 1e3:.0f} uT, "
    f"{D['world']['f_L'][0]:.0f}-{D['world']['f_L'][1]:.0f} Hz: SW1 reaches it everywhere with the coil above.",
    "4  MODE RUN, SEQUENCE TIMER: RV1 sets how long it polarizes, RV2 how long it listens; or drive POLARIZE IN.",
    "5  Watch OUT on a scope, triggered on SYNC OUT falling; CAL IN puts a known signal into the tank.",
    "6  Or listen: headphones in PHONES, VOLUME clockwise louder.  Start it low: OUT can hit the rails at a switch-off.",
    "CAUTION: the coil and Q1's drain reach about 130 V for half a millisecond at every switch-off.",
    "Copper: 1 (top) every drawn wire; 2 ground; 3 +15 V; 4 -15 V and the three hops.",
]
