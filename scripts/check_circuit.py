#!/usr/bin/env python3
"""Read the exported netlist back against the circuit as designed.

    python3 scripts/check_circuit.py out/earthnmr.net

The schematic is drawn by hand-placed coordinates, and a wire laid over a pin
or a ground symbol on a bus joins nets silently: ERC passes, the netlist is
wrong.  So the circuit is written down here a second time, net by net, as the
set of pins each net must hold -- every net, exactly -- and every value the
design arithmetic chose (sim/design.json) is asserted against the value the
netlist carries.  A difference in either fails the build.
"""
import json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexp_parse import parse_file
import parts

DESIGN = os.path.join(ROOT, "sim", "design.json")


def ohms(text):
    t = text.replace("Ω", "").replace("ohm", "")
    m = re.fullmatch(r"([\d.]+)([RkM]?)([\d]*)", t)
    if not m:
        raise ValueError(text)
    a, mult, b = m.groups()
    v = float(a + ("." + b if b else ""))
    return v * {"": 1, "R": 1, "k": 1e3, "M": 1e6}[mult]


def farads(text):
    m = re.fullmatch(r"([\d.]+)([pnu])F?", text)
    return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6}[m.group(2)]


class Netlist:
    def __init__(self, path):
        root = parse_file(path)
        self.value, self.fp, self.fields = {}, {}, {}
        for c in root.first("components").kids("comp"):
            ref = c.first("ref").atom(0)
            self.value[ref] = c.first("value").atom(0)
            self.fp[ref] = c.first("footprint").atom(0)
            f = {}
            fl = c.first("fields")
            if fl is not None:
                for x in fl.kids("field"):
                    f[x.first("name").atom(0)] = x.atom(0)
            self.fields[ref] = f
        self.nets, self.net_of = {}, {}
        for n in root.first("nets").kids("net"):
            name = n.first("name").atom(0)
            pins = {f"{x.first('ref').atom(0)}.{x.first('pin').atom(0)}" for x in n.kids("node")}
            self.nets[name] = pins
            for p in pins:
                self.net_of[p] = name

    def members(self, pin):
        return self.nets.get(self.net_of.get(pin), set())


def rng(prefix, a, b, pin):
    return {f"{prefix}{i}.{pin}" for i in range(a, b + 1)}


# The bypass capacitors: one 100 nF per supply pin, in drawing order C80...
# OPA197 U1-U7: V+ then V-; the comparators U8? (drawn later), U9, U10 and the
# timer: V+ only.  Which pin each one serves is checked by its net below.
def expected(D):
    """Every net, as the set of pins it must hold."""
    bank_parts = [len(b["parts"]) for b in D["bank"]["switches"]]
    caps, c = [], 10
    for n in bank_parts:
        caps.append([f"C{c + i}" for i in range(n)])
        c += n
    E = {}

    def net(name, *groups):
        s = set()
        for gr in groups:
            s |= set(gr) if not isinstance(gr, str) else {gr}
        E[name] = s

    # power entry
    net("+15V_IN", "J1.1", "D1.2")
    net("-15V_IN", "J1.3", "D2.1")
    # the polarizing supply and switch
    net("POLSUP", "J2.1", "F1.1")
    net("V_POL", "F1.2", "D5.1", "D6.1", "C5.1", "R3.1", "K1.5", "TP1.1")
    net("LED3", "R3.2", "LED3.2")
    net("COIL_A", "J3.2", "K1.4")
    net("COIL_B", "J3.1", "K1.9")
    net("DRAIN", "K1.8", "Q1.2", "D7.1", "TP2.1")
    net("SOURCE", "Q1.3", "D7.2", "R4.1", "R6.2", "TP3.1")
    net("GATE_Q", "Q1.1", "R5.2", "R6.1")
    net("GATE", "R5.1", "R7.2", "U9.1", "TP4.1")
    # the tank
    net("TANK+", "K1.3", "D9.2", "R14.2", "R15.1", "TP5.1", {f"SW1.{p}" for p in range(9, 17)})
    net("TANK-", "K1.10", "D9.1", "R16.1", "TP6.1", {f"{ref}.2" for grp in caps for ref in grp})
    for k, grp in enumerate(caps):
        net(f"BANK{k + 1}", f"SW1.{k + 1}", {f"{ref}.1" for ref in grp})
    net("CAL", "J4.1", "R13.1", "R14.1")
    # the instrumentation amplifier
    net("U1+", "R15.2", "R11.2", "U1.3")
    net("U2+", "R16.2", "R12.1", "U2.3")
    net("U1-", "U1.4", "R19.1", "R17.1")
    net("U2-", "U2.4", "R19.2", "R18.1")
    net("INA_A", "U1.1", "R17.2", "R21.1", "TP7.1")
    net("INA_B", "U2.1", "R18.2", "R20.1", "TP8.1")
    net("U3+", "R21.2", "R22.2", "U3.3")
    net("U3-", "R20.2", "R23.1", "U3.4")
    net("PREAMP", "U3.1", "R23.2", "C30.1", "TP9.1")
    # the filters: (series a, series b, feedback, shunt, op-amp)
    net("HP1_A", "C30.2", "C31.1", "R24.1")
    net("U4+", "C31.2", "R25.1", "U4.3")
    net("HP1", "U4.1", "U4.4", "R24.2", "C32.1", "TP10.1")
    net("HP2_A", "C32.2", "C33.1", "R26.1")
    net("U5+", "C33.2", "R27.1", "U5.3")
    net("HP", "U5.1", "U5.4", "R26.2", "R28.1", "TP11.1")
    net("LP_A", "R28.2", "R29.1", "C34.1")
    net("U6+", "R29.2", "C35.1", "U6.3")
    net("LP", "U6.1", "U6.4", "C34.2", "U7.3", "TP12.1")
    # the gain stage and the outputs
    net("U7-", "U7.4", "R30.1", "SW2.2")
    net("GAIN_LO", "SW2.1", "R31.2")
    net("GAIN_HI", "SW2.3", "R32.2")
    net("OUT", "U7.1", "R30.2", "R33.1", "TP13.1", "R58.1")
    net("OUT_J", "R33.2", "J5.1")
    # HEADPHONES: OUT through R58 onto the VOLUME knob's clockwise end, its wiper into U12,
    # a follower; each earpiece through its own 100 ohm, tip (left) and ring (right) alike
    net("VOL_TOP", "R58.2", "RV3.3")
    net("VOL_WIPER", "RV3.2", "U12.3")
    net("PHONES", "U12.1", "U12.4", "TP22.1", "R56.1", "R57.1")
    net("PHONES_T", "R56.2", "J9.T")
    net("PHONES_R", "R57.2", "J9.R")
    # the timer
    net("DIS", "U11.7", "RV1.2", "RV1.3", "D10.2", "RV2.1")
    net("RA", "R40.2", "RV1.1")
    net("CT", "U11.2", "U11.6", "D10.1", "D11.2", "C50.1", "C51.1", "C52.1", "TP18.1")
    net("RB", "RV2.2", "RV2.3", "R41.1")
    net("RB_D", "R41.2", "D11.1")
    net("CTRL", "U11.5", "C53.2")
    net("INT", "U11.3", "SW3.3")
    # POLARIZE IN
    net("EXT_J", "J7.1", "R43.1", "R44.1")
    net("EXT_CLAMP", "R44.2", "D12.3", "R47.1", "R59.1")      # the clamped node: D12 and the hysteresis
    net("U8+", "R59.2", "U8.4")                                # the comparator's own pin, behind R59
    net("U8-", "U8.3", "R45.2", "R46.1")
    net("EXT", "U8.1", "R47.2", "R48.2", "SW3.1", "TP19.1")
    net("SEQ", "SW3.2", "SW4.1")
    net("POL_CMD", "SW4.2", "R42.1", "TP14.1", "R49.1", "D13.1", "D14.2", "R50.1", "R53.1")
    # the delays
    net("VTH", "R51.2", "R52.1", "C54.1", "U9.3", "U10.3")
    net("DELAY", "R49.2", "D13.2", "C55.1", "U9.4", "TP15.1")
    net("HOLD", "R50.2", "D14.1", "C56.1", "U10.4", "TP16.1")
    net("RELAY", "U10.1", "R9.2", "R8.1", "TP17.1")
    net("Q2B", "R8.2", "Q2.1")
    net("COIL-", "K1.12", "Q2.3", "D8.2", "LED4.1")
    net("LED4", "R10.2", "LED4.2")
    # SYNC OUT
    net("Q3B", "R53.2", "Q3.1")
    net("Q3E", "Q3.2", "R54.1", "R55.1")
    net("SYNC_J", "R55.2", "J8.1")
    # the lamps
    net("LED1", "R1.2", "LED1.2")
    net("LED2", "R2.1", "LED2.1")
    return E


RAIL_P = ({f"U{i}.5" for i in range(1, 13) if i != 11} | {"U11.4", "U11.8", "D1.1", "D3.1", "D8.1", "D12.2", "K1.1",
          "Q3.3", "R1.1", "R7.1", "R9.1", "R10.1", "R40.1", "R45.1", "R48.1", "R51.1", "TP20.1", "C1.1", "C3.1"})
RAIL_M = {f"U{i}.2" for i in (1, 2, 3, 4, 5, 6, 7, 12)} | {"D2.2", "D4.2", "R2.2", "TP21.1", "C2.2", "C4.2"}
GND_FIXED = ({"J1.2", "J2.2", "J3.3", "J4.2", "J5.2", "J7.2", "J8.2", "D3.2", "D4.1", "D5.2", "D6.2",
              "D12.1", "LED1.1", "LED2.2", "LED3.1", "Q2.2", "R4.2", "R11.1", "R12.2", "R13.2", "R22.1", "R25.2",
              "R27.2", "R31.1", "R32.1", "R42.2", "R43.2", "R46.2", "R52.2", "R54.2", "SW4.3",
              "U8.2", "U9.2", "U10.2", "U11.1", "C1.2", "C2.1", "C3.2", "C4.1", "C5.2", "C35.2", "C50.2", "C51.2",
              "C52.2", "C53.1", "C54.2", "C55.2", "C56.2", "RV3.1", "J9.S"} | {f"TP{i}.1" for i in range(100, 104)})


def main(path):
    D = json.load(open(DESIGN))
    nl = Netlist(path)
    fails, n = [], [0]

    def check(cond, what):
        n[0] += 1
        if not cond:
            fails.append(what)

    E = expected(D)
    # every designed net exists exactly
    claimed = set()
    for name, pins in E.items():
        rep = sorted(pins)[0]
        got = nl.members(rep)
        check(got == pins, f"net {name}: expected {sorted(pins)}, the netlist has {sorted(got)} "
                           f"(extra {sorted(got - pins)}, missing {sorted(pins - got)})")
        claimed |= pins
    # the rails: their fixed members, plus bypass capacitors and nothing else
    byp = {r for r in nl.value if re.fullmatch(r"C(8\d|9\d)", r)}
    for rail, fixed, side in (("+15V", RAIL_P, "1"), ("-15V", RAIL_M, "1"), ("GND", GND_FIXED, "2")):
        got = nl.nets.get(rail, set())
        extra = {p for p in got - fixed if not (p.split(".")[0] in byp)}
        check(not extra, f"{rail} carries pins it should not: {sorted(extra)}")
        check(fixed <= got, f"{rail} is missing {sorted(fixed - got)}")
        claimed |= got
    # each bypass capacitor between one rail and ground, and each supply pin with its own
    for r in sorted(byp):
        a, b = nl.net_of.get(f"{r}.1"), nl.net_of.get(f"{r}.2")
        check({a, b} in ({"+15V", "GND"}, {"-15V", "GND"}), f"{r} is between {a} and {b}, not a rail and ground")
        check(nl.value[r] == "100nF", f"{r} is {nl.value[r]}, not 100nF")
    np_ = sum(1 for r in byp if "+15V" in (nl.net_of.get(f"{r}.1"), nl.net_of.get(f"{r}.2")))
    nm_ = sum(1 for r in byp if "-15V" in (nl.net_of.get(f"{r}.1"), nl.net_of.get(f"{r}.2")))
    check(np_ == 12 and nm_ == 8, f"bypass: {np_} on +15V (want 12: U1-U10, U12 and the timer), {nm_} on -15V (want 8)")
    # nothing left over: every pin of every part is on a net this check knows
    every = {p for pins in nl.nets.values() for p in pins}
    check(every <= claimed, f"pins on nets nobody designed: {sorted(every - claimed)}")
    # every part has its order code, and its value is the parts table's
    for ref, val in nl.value.items():
        if ref.startswith(("#", "MH")):
            continue
        check("LCSC" in nl.fields[ref], f"{ref} ({val}) has no LCSC code")
    # ------------------------------------------------- the design values --
    def R(ref):
        return ohms(nl.value[ref])

    def C(ref):
        return farads(nl.value[ref])

    ina = D["ina"]
    check(R("R15") == R("R16") == ohms(ina["R_series"]), "R15, R16: the input series resistors")
    check(R("R11") == R("R12") == ohms(ina["R_bias"]), "R11, R12: the bias resistors")
    g_ina = 1 + (R("R17") + R("R18")) / R("R19")
    check(abs(g_ina - ina["gain"]) < 1e-6 and R("R17") == R("R18"), f"INA gain {g_ina:.1f} != {ina['gain']:.1f}")
    check(R("R20") == R("R21") == R("R22") == R("R23"), "U3's four resistors must match (CMRR)")
    for (ra, rb, ca, cb, key) in (("R24", "R25", "C30", "C31", "hp1"), ("R26", "R27", "C32", "C33", "hp2")):
        f0 = 1 / (2 * math.pi * C(ca) * math.sqrt(R(ra) * R(rb)))
        q = 0.5 * math.sqrt(R(rb) / R(ra))
        check(C(ca) == C(cb), f"{ca}, {cb} equal")
        check(abs(f0 - D[key]["f0"]) < 0.5 and abs(q - D[key]["Q"]) < 1e-3,
              f"{key}: the netlist's f0 {f0:.1f} Hz Q {q:.3f}, the design's {D[key]['f0']:.1f} {D[key]['Q']:.3f}")
    r1, r2, c1, c2 = R("R28"), R("R29"), C("C34"), C("C35")
    f0 = 1 / (2 * math.pi * math.sqrt(r1 * r2 * c1 * c2))
    q = math.sqrt(r1 * r2 * c1 * c2) / (c2 * (r1 + r2))
    check(abs(f0 - D["lp"]["f0"]) < 0.5 and abs(q - D["lp"]["Q"]) < 1e-3, f"lp: f0 {f0:.1f} Q {q:.3f}")
    gn = D["gain"]
    check(abs(1 + R("R30") / R("R31") - gn["lo"]) < 1e-6, "LOW gain (R30, R31 on SW2 pole 1)")
    check(abs(1 + R("R30") / R("R32") - gn["hi"]) < 1e-6, "HIGH gain (R30, R32 on SW2 pole 3)")
    # the bank's weights, and the parts that make them
    for k, b in enumerate(D["bank"]["switches"]):
        refs = sorted((p.split(".")[0] for p in E[f"BANK{k + 1}"] if p.startswith("C")), key=lambda r: int(r[1:]))
        tot = sum(C(r) for r in refs)
        check(abs(tot - b["C"]) < 1e-12, f"bank switch {k + 1}: {tot * 1e9:.2f} nF, designed {b['C'] * 1e9:.2f}")
        for r in refs:
            code = nl.fields[r].get("LCSC")
            p = parts.PASSIVES.get({"100nF": "100nF_C0G"}.get(nl.value[r], nl.value[r]))
            check(p is not None and code == p["lcsc"] and "C0G" in p["note"],
                  f"{r}: {nl.value[r]} {code} is not the C0G part")
    for r in ("C30", "C31", "C32", "C33", "C34", "C35"):
        p = parts.PASSIVES[nl.value[r]]
        check(nl.fields[r].get("LCSC") == p["lcsc"] and "C0G" in p["note"], f"{r}: a filter capacitor must be C0G")
    # the headphones: the knob's range, the earpieces' series resistors, the jack's pins
    ph = D["phones"]
    check(R("R58") == ohms(ph["R_feed"]) and nl.value["RV3"] == ph["RV"], "R58, RV3: the headphones' level")
    check(R("R56") == R("R57") == ohms(ph["R_out"]), "R56, R57: one per earpiece")
    check(nl.fields["J9"].get("LCSC") == parts.PARTS["JACK"]["lcsc"] and nl.fields["RV3"].get("LCSC")
          == parts.PARTS["POT_KNOB"]["lcsc"], "J9 is the SJ1-3523N, RV3 the RK09K")
    check(nl.net_of["J9.S"] == "GND", "J9: the sleeve on ground")
    check(nl.net_of["RV3.1"] == "GND" and nl.net_of["RV3.3"] == nl.net_of["R58.2"],
          "RV3: pin 3, the clockwise end, from R58 (clockwise louder), pin 1 to ground")
    # the timer and the delays
    tm = D["timer"]
    check(R("R40") == R("R41") == ohms(tm["R_min"]), "R40, R41: the timer's minimum resistance")
    check(nl.value["RV1"] == nl.value["RV2"] == tm["RV"], "RV1, RV2")
    check(all(nl.value[f"C{50 + i}"] == tm["C"] for i in range(tm["n_C"])), "C50-C52: the timer's film capacitors")
    check(all(nl.fields[f"C{50 + i}"].get("LCSC") == parts.PARTS["CFILM"]["lcsc"] for i in range(tm["n_C"])),
          "C50-C52 are the polypropylene film part")
    dl = D["delay"]
    check(R("R49") == ohms(dl["R_gate"]) and R("R50") == ohms(dl["R_hold"]), "R49, R50: the gate delay and the hold")
    for r in ("C55", "C56"):
        check(nl.fields[r].get("LCSC") == parts.PASSIVES["100nF_C0G"]["lcsc"], f"{r}: a timing capacitor must be C0G")
    check(R("R51") == ohms(dl["R_th_top"]) and R("R52") == ohms(dl["R_th_bot"]), "R51, R52: the threshold")
    ex = D["ext"]
    check(R("R45") == ohms(ex["R_top"]) and R("R46") == ohms(ex["R_bot"]) and R("R47") == ohms(ex["R_hyst"]),
          "U8's threshold and hysteresis")
    check(R("R44") == ohms(ex["R_series"]) and R("R59") == ohms(ex["R_in"]) and R("R43") == ohms(ex["R_pd"]),
          "POLARIZE IN: R44 ahead of the clamp, R59 behind it, R43 the pull-down")
    check(nl.net_of["D12.1"] == "GND" and nl.net_of["D12.2"] == "+15V",
          "D12: anode 1 on ground, cathode 2 on +15 V (the BAT54S's series pair clamps the node between them)")
    check(R("R7") == ohms(D["gate"]["R_pu"]) and R("R5") == ohms(D["gate"]["R_g"]) and R("R6") == ohms(D["gate"]["R_gs"]),
          "the gate's pull-up, series and pull-down")
    # polarities
    check(nl.net_of["D1.2"] == "/+15V_IN" and nl.net_of["D1.1"] == "+15V", "D1: anode from J1, cathode to +15V")
    check(nl.net_of["D2.1"] == "/-15V_IN" and nl.net_of["D2.2"] == "-15V", "D2: cathode to J1, anode from -15V")
    check(nl.net_of["D7.1"] == "/DRAIN" and nl.net_of["D7.2"] == "/SOURCE", "D7: cathode on the drain")
    check(nl.net_of["D8.1"] == "+15V", "D8: the relay's freewheel diode, cathode on +15V")
    check(nl.net_of["K1.1"] == "+15V", "K1: coil pin 1 (+) on +15V, as the HFD3 wants")
    check(nl.net_of["C5.1"] == "/V_POL" and nl.net_of["C2.1"] == "GND" and nl.net_of["C1.1"] == "+15V",
          "the electrolytics' + ends")
    # the parts are the parts table's
    for ref, key in (("U1", "OPAMP"), ("U8", "COMP"), ("U9", "COMP"), ("U10", "COMP"), ("U11", "TIMER"),
                     ("Q1", "MOSFET"), ("K1", "RELAY"), ("D7", "TVS_CLAMP"), ("D9", "TVS_TANK"),
                     ("D6", "TVS_SUPPLY"), ("F1", "PTC"), ("R4", "RSENSE"), ("SW1", "DIP8"), ("D12", "DCLAMP")):
        check(nl.fields[ref].get("LCSC") == parts.PARTS[key]["lcsc"], f"{ref} is not {parts.PARTS[key]['mpn']}")
    print(f"  {n[0]} circuit checks, {len(fails)} failed")
    for f in fails:
        print(f"  !! {f}")
    if not fails:
        print("  all circuit checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "out", "earthnmr.net")))
