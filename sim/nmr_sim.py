#!/usr/bin/env python3
"""Simulate the board from its exported netlist with ngspice.

    python3 sim/nmr_sim.py [--plots]      writes sim/results.json (and docs/images/sim_*.png)

Three decks, each written from out/earthnmr.net (every resistor, capacitor,
switch and op-amp the schematic draws, by its reference and value), so a
wiring mistake on the sheet shows up here as a wrong answer:

  1. LISTEN, small signal: the reference coil (sim/design.py) with an EMF in
     series, the relay's normally-closed contacts, the tank with the DIP set
     for the coil, the preamplifier, the filters and the gain stage, in both
     GAIN positions.  AC transfer to OUT, the same through CAL IN, and the
     noise at OUT (every resistor's thermal noise plus each OPA197's 5.5
     nV/rtHz as an equivalent resistor at its + input).
  2. SWITCH-OFF: the polarizing loop with the relay energized: the supply, the
     fuse, the reservoir, the coil, the MOSFET as a switch, the SMCJ100A as a
     breakdown diode, the sense resistor.  The ramp, the drain's peak, the
     clamp's energy.
  3. SEQUENCER: POL CMD stepped up and down into the two delays (R49/D13/C55,
     R50/D14/C56), the threshold divider and the comparators: when GATE and
     RELAY move.

Models are behavioural and stated where they are made.  The answers are the
board's as fitted (the netlist's values), and sim/design.py's figures are
checked against them in check(): the analysis and the arithmetic agree or the
build stops.
"""
import json, math, os, re, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sexp_parse import parse_file          # noqa: E402

NETLIST = os.path.join(ROOT, "out", "earthnmr.net")
DESIGN = os.path.join(ROOT, "sim", "design.json")
RESULTS = os.path.join(ROOT, "sim", "results.json")
IMAGES = os.path.join(ROOT, "docs", "images")
K_B, T = 1.380649e-23, 300.0
EN_OPA197 = 5.5e-9
R_NOISE = EN_OPA197 ** 2 / (4 * K_B * T)          # 1.83 k: the resistor whose noise is the op-amp's


def spice_name(net):
    if net == "GND":
        return "0"
    n = net.lstrip("/").replace("+", "P").replace("-", "M")
    n = re.sub(r"[^A-Za-z0-9_]", "_", n).strip("_")
    return "n_" + n


def value_si(text):
    t = text.strip().replace("Ω", "")
    m = re.fullmatch(r"([0-9.]+)([RkMunp]?)([0-9]*)F?", t)
    if not m:
        raise ValueError(text)
    a, mult, b = m.groups()
    v = float(a + ("." + b if b else ""))
    return v * {"": 1, "R": 1, "k": 1e3, "M": 1e6, "u": 1e-6, "n": 1e-9, "p": 1e-12}[mult]


class Netlist:
    def __init__(self, path=NETLIST):
        if not os.path.exists(path):
            raise SystemExit(f"{os.path.relpath(path, ROOT)} is missing: build the schematic first (./make.py --stage sch)")
        root = parse_file(path)
        self.value = {c.first("ref").atom(0): c.first("value").atom(0) for c in root.first("components").kids("comp")}
        self.net = {}
        for n in root.first("nets").kids("net"):
            name = spice_name(n.first("name").atom(0))
            for x in n.kids("node"):
                self.net[(x.first("ref").atom(0), x.first("pin").atom(0))] = name

    def pin(self, ref, p):
        return self.net[(ref, str(p))]


OPAMP = """
* OPA197, behavioural: 120 dB, one pole, 10 MHz gain-bandwidth, 10 ohm out
.subckt OPA out inp inn vp vm
Rin inp inn 1e12
Eg n1 0 inp inn 1e6
R1 n1 n2 1k
C1 n2 0 15.9u
Eo out 0 n2 0 1
.ends OPA
"""


def receive_deck(nl, D, gain, source="emf"):
    """The LISTEN state's small-signal deck.  source: 'emf' (in the coil) or 'cal' (CAL IN)."""
    c = D["coil"]
    code = c["dip_code"]
    L = ["* LISTEN: the receiver from the netlist", OPAMP,
         "Vp n_p15 0 14.67", "Vm n_m15 0 -14.67"]
    rails = {"+15V": "n_p15", "-15V": "n_m15"}
    for ref, val in sorted(nl.value.items()):
        kind = re.match(r"[A-Z]+", ref).group(0)
        if kind == "R" and ref not in ("R4",):
            a, b = nl.pin(ref, 1), nl.pin(ref, 2)
            if {a, b} & {"n_P15V", "n_M15V"}:
                a = {"n_P15V": "n_p15", "n_M15V": "n_m15"}.get(a, a)
                b = {"n_P15V": "n_p15", "n_M15V": "n_m15"}.get(b, b)
            L.append(f"R{ref} {a} {b} {value_si(val):g}")
        elif kind == "C" and val not in ("100uF", "470uF"):
            a = {"n_P15V": "n_p15", "n_M15V": "n_m15"}.get(nl.pin(ref, 1), nl.pin(ref, 1))
            b = {"n_P15V": "n_p15", "n_M15V": "n_m15"}.get(nl.pin(ref, 2), nl.pin(ref, 2))
            L.append(f"C{ref} {a} {b} {value_si(val):g}")
        elif ref in [f"U{i}" for i in range(1, 8)]:
            # the op-amp's noise as a resistor in series with its + input
            L.append(f"Rn{ref} {nl.pin(ref, 3)} {ref}_p {R_NOISE:.1f}")
            L.append(f"X{ref} {nl.pin(ref, 1)} {ref}_p {nl.pin(ref, 4)} n_p15 n_m15 OPA")
        elif ref == "SW1":                      # the bank, set for the coil
            for k in range(1, 9):
                on = code >> (k - 1) & 1
                L.append(f"RSW1_{k} {nl.pin(ref, k)} {nl.pin(ref, 17 - k)} {0.05 if on else 1e12:g}")
        elif ref == "SW2":                      # GAIN: 1 = LOW, 3 = HIGH
            on, off = (1, 3) if gain == "lo" else (3, 1)
            L.append(f"RSW2on {nl.pin(ref, 2)} {nl.pin(ref, on)} 0.05")
            L.append(f"RSW2off {nl.pin(ref, 2)} {nl.pin(ref, off)} 1e12")
        elif ref == "D9":                       # the tank's clamp: its 390 pF, idle
            L.append(f"CD9 {nl.pin(ref, 1)} {nl.pin(ref, 2)} 390p")
    # the relay released: commons on the normally-closed contacts
    L.append(f"RK1a {nl.pin('K1', 4)} {nl.pin('K1', 3)} 0.1")
    L.append(f"RK1b {nl.pin('K1', 9)} {nl.pin('K1', 10)} 0.1")
    # the coil between COIL_A and COIL_B: the EMF, its resistance, its inductance
    a, b = nl.pin("J3", 1), nl.pin("J3", 2)
    emf = "AC 1" if source == "emf" else "0"
    L.append(f"Vemf {a} coil_x {emf}")
    L.append(f"Rcoil coil_x coil_y {c['R']:.4f}")
    L.append(f"Lcoil coil_y {b} {c['L']:.6f}")
    # CAL IN: a 50 ohm generator, or idle into its 51 ohm termination
    j4 = nl.pin("J4", 1)
    L.append(f"Vcal cal_s 0 {'AC 1' if source == 'cal' else '0'}")
    L.append(f"Rgen cal_s {j4} 50")
    # OUT into a 1 Mohm scope
    L.append(f"Rscope {nl.pin('J5', 1)} 0 1e6")
    return leak(L)


def leak(L):
    """1 Tohm from every node to ground: the parts this deck leaves out would
    otherwise leave their nets floating (a singular matrix)."""
    nodes = set()
    for ln in L:
        f = ln.split()
        if not f or ln.startswith(("*", ".", "V", "E", "R1", "C1")) and not ln.startswith(("RU", "Rn", "RK", "RSW")):
            pass
        if f and f[0][0] in "RCLDS" and not ln.startswith(".") and len(f) >= 3:
            nodes |= {f[1], f[2]}
    return L + [f"Rleak_{i} {n} 0 1e12" for i, n in enumerate(sorted(nodes - {"0"}))]


def run(deck_lines, control):
    with tempfile.TemporaryDirectory() as td:
        cir = os.path.join(td, "deck.cir")
        out = os.path.join(td, "out.txt")
        with open(cir, "w") as fh:
            fh.write("\n".join(deck_lines) + "\n.control\n" + control.replace("@OUT@", out) + "\n.endc\n.end\n")
        r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, timeout=600)
        if not os.path.exists(out):
            raise SystemExit("ngspice failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])
        rows = []
        for line in open(out):
            parts = line.split()
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                continue
        return rows


def ac(nl, D, gain, source="emf", sweep="dec 400 20 100k"):
    out = nl.pin("U7", 1)
    tank_p, tank_m = nl.pin("K1", 3), nl.pin("K1", 10)
    rows = run(receive_deck(nl, D, gain, source),
               f"ac {sweep}\nwrdata @OUT@ mag(v({out})) mag(v({tank_p})-v({tank_m})) mag(v({nl.pin('U3', 1)}))")
    # wrdata writes (f, value) pairs per vector
    return [(r[0], r[1], r[3], r[5]) for r in rows]


def noise(nl, D, gain):
    out = nl.pin("U7", 1)
    rows = run(receive_deck(nl, D, gain, "emf"),
               f"noise v({out}) Vemf dec 200 100 100k\nsetplot noise1\nwrdata @OUT@ onoise_spectrum inoise_spectrum")
    return [(r[0], r[1], r[3]) for r in rows]


def interp(rows, f, col=1):
    for a, b in zip(rows, rows[1:]):
        if a[0] <= f <= b[0]:
            t = (math.log(f) - math.log(a[0])) / (math.log(b[0]) - math.log(a[0]))
            return a[col] + t * (b[col] - a[col])
    raise ValueError(f)


def switch_off(nl, D, v_supply=None):
    """The polarizing loop, relay energized, the switch opening at t0."""
    c = D["coil"]
    v_supply = v_supply or c["V_pol"] + c["I_pol"] * 0.13
    L = ["* SWITCH-OFF: the polarizing loop from the netlist",
         ".model DTVS D(BV=117 IBV=1m RS=4.2 CJO=2n)",
         ".model DSCH D(IS=5u RS=0.03 N=1.1 BV=40)",
         ".model DTVS33 D(BV=36.7 IBV=1m RS=1.5)",
         ".model SWQ SW(VT=5 VH=0.1 RON=0.026 ROFF=1e8)"]
    vpol = nl.pin("F1", 1)
    L.append(f"Vsup sup 0 {v_supply:.3f}")
    L.append(f"Rlead sup {vpol} 0.1")                              # the bench leads
    L.append(f"RF1 {nl.pin('F1', 1)} {nl.pin('F1', 2)} 0.03")         # the PTC, cold
    L.append(f"CC5 {nl.pin('C5', 1)} 0 470u")
    L.append(f"DD6 {nl.pin('D6', 2)} {nl.pin('D6', 1)} DTVS33")
    L.append(f"DD5 {nl.pin('D5', 2)} {nl.pin('D5', 1)} DSCH")
    # relay energized: commons on the normally-open contacts
    L.append(f"RK1a {nl.pin('K1', 4)} {nl.pin('K1', 5)} 0.05")
    L.append(f"RK1b {nl.pin('K1', 9)} {nl.pin('K1', 8)} 0.05")
    a, b = nl.pin("J3", 1), nl.pin("J3", 2)
    L.append(f"Rcoil {a} coil_y {c['R']:.4f}")
    L.append(f"Lcoil coil_y {b} {c['L']:.6f} IC=0")
    L.append(f"Ccoil {a} {b} 200p")                                   # its self-capacitance
    drain, src = nl.pin("Q1", 2), nl.pin("Q1", 3)
    L.append("Vg g 0 PULSE(0 10 1m 10u 10u 40m 1)")                   # on at 1 ms, off at 41 ms
    L.append(f"SQ1 {drain} {src} g 0 SWQ")
    L.append(f"Coss {drain} {src} 400p")
    L.append(f"DD7 {nl.pin('D7', 2)} {nl.pin('D7', 1)} DTVS")
    L.append(f"RR4 {nl.pin('R4', 1)} {nl.pin('R4', 2)} 0.1")
    rows = run(L, f"tran 2u 50m 0 2u\nwrdata @OUT@ v({drain}) i(Vsup) v({src})")
    return [(r[0], r[1], -r[3], r[5]) for r in rows], v_supply


def sequencer(nl, D):
    """POL CMD up at 10 ms and down at 210 ms, into the two delays."""
    v_oh = 14.67 - 1.4
    L = ["* SEQUENCER: the gate delay and the relay hold from the netlist",
         ".model D4148 D(IS=2.5n N=1.75 RS=0.6 CJO=2p)",
         ".model SWC SW(VT=0 VH=0.01 RON=30 ROFF=1e9)",
         "Vp n_p15 0 14.67"]
    pc = nl.pin("R42", 1)
    L.append(f"Vcmd {pc} 0 PULSE(0 {v_oh:.2f} 10m 1u 1u 200m 1)")
    take = {"R49", "R50", "R51", "R52", "R7", "R9", "C55", "C56", "C54", "D13", "D14"}
    for ref in sorted(take):
        val = nl.value[ref]
        a, b = nl.pin(ref, 1), nl.pin(ref, 2)
        a = "n_p15" if a == "n_P15V" else a
        b = "n_p15" if b == "n_P15V" else b
        if ref.startswith("R"):
            L.append(f"R{ref} {a} {b} {value_si(val):g}")
        elif ref.startswith("C"):
            L.append(f"C{ref} {a} {b} {value_si(val):g}")
        else:
            L.append(f"D{ref} {b} {a} D4148")
    # TS391: open collector -- the output transistor is on while IN+ < IN-
    for u in ("U9", "U10"):
        L.append(f"S{u} {nl.pin(u, 1)} 0 {nl.pin(u, 3)} {nl.pin(u, 4)} SWC")
    L.append(f"Rgate_load {nl.pin('U9', 1)} 0 1e6")
    rows = run(leak(L), f"tran 20u 300m\nwrdata @OUT@ v({nl.pin('U9', 1)}) v({nl.pin('U10', 1)}) v({pc})")
    return [(r[0], r[1], r[3], r[5]) for r in rows]


def crossing(rows, col, level, after, rising):
    for a, b in zip(rows, rows[1:]):
        if a[0] < after:
            continue
        if (rising and a[col] < level <= b[col]) or (not rising and a[col] > level >= b[col]):
            return a[0] + (level - a[col]) / (b[col] - a[col]) * (b[0] - a[0])
    return None


def main(plots=False):
    D = json.load(open(DESIGN))
    nl = Netlist()
    R = {}
    fL = D["site"]["f_L"]
    for gain in ("lo", "hi"):
        rows = ac(nl, D, gain)
        g_out = interp(rows, fL)
        g_tank = interp(rows, fL, 2)
        fine = ac(nl, D, gain, sweep=f"lin 2001 {fL * 0.85:.1f} {fL * 1.15:.1f}")
        peak = max(fine, key=lambda r: r[2])
        half = [r[0] for r in fine if r[2] >= peak[2] / math.sqrt(2)]
        R[f"ac_{gain}"] = dict(out_per_emf=g_out, tank_per_emf=g_tank, f_tank_peak=peak[0],
                               tank_bw=half[-1] - half[0], q_tank=peak[0] / (half[-1] - half[0]),
                               out_60=interp(rows, 60.0), out_180=interp(rows, 180.0),
                               chain_gain=g_out / g_tank)
        if gain == "hi":
            R["ac_curve"] = [(round(r[0], 2), r[1], r[2]) for r in rows[::4]]
    cal = ac(nl, D, "lo", source="cal")
    R["cal_lo_per_volt"] = interp(cal, fL)
    nz = noise(nl, D, "hi")
    R["noise"] = dict(in_at_fL=interp(nz, fL, 2), out_at_fL=interp(nz, fL, 1))
    # the output noise in the tank's bandwidth and over the whole band
    band = [r for r in nz if 500 <= r[0] <= 5000]
    tot = sum(((b[0] - a[0]) * (a[1] ** 2 + b[1] ** 2) / 2) for a, b in zip(band, band[1:]))
    R["noise"]["out_rms_band"] = math.sqrt(tot)
    R["noise"]["coil_thermal"] = math.sqrt(4 * K_B * T * D["coil"]["R"])
    # the FID at OUT on HIGH
    R["fid_out_hi"] = D["coil"]["emf"] * R["ac_hi"]["out_per_emf"]
    R["snr_db"] = 20 * math.log10(R["fid_out_hi"] / (math.sqrt(2) * R["noise"]["out_at_fL"]
                                                    * math.sqrt(D["noise"]["nbw"])))
    # the switch-off
    rows, vs = switch_off(nl, D)
    i_on = max(r[2] for r in rows if 30e-3 < r[0] < 41e-3)
    v_peak = max(r[1] for r in rows)
    t_off = 41e-3 + 10e-6
    i_src = [(r[0], (r[3]) / 0.1) for r in rows]          # the coil current, from the sense resistor
    t90 = next(t for t, i in i_src if t > t_off and i < 0.9 * i_on)
    t10 = next(t for t, i in i_src if t > t_off and i < 0.1 * i_on)
    e_tvs = 0.0
    for a, b in zip(rows, rows[1:]):
        if a[0] > t_off and a[1] > 100:
            e_tvs += (b[0] - a[0]) * a[1] * (a[3] / 0.1)
    R["switch_off"] = dict(v_supply=vs, i_on=i_on, v_drain_peak=v_peak, ramp_90_10=t10 - t90,
                           ramp_full=(t10 - t90) / 0.8, e_tvs=e_tvs, e_coil=0.5 * D["coil"]["L"] * i_on ** 2)
    if plots:
        R["_switch_rows"] = [(r[0], r[1], r[3] / 0.1) for r in rows if 40e-3 < r[0] < 43e-3]
    # the sequencer
    sq = sequencer(nl, D)
    hi = 7.0
    t_gate_on = crossing(sq, 1, hi, 10e-3, True)
    t_gate_off = crossing(sq, 1, hi, 200e-3, False)
    t_rel_on = crossing(sq, 2, hi, 5e-3, True)
    t_rel_off = crossing(sq, 2, hi, 200e-3, False)
    R["sequencer"] = dict(gate_delay=t_gate_on - 10e-3, gate_off_lag=t_gate_off - 210e-3,
                          relay_on_lag=t_rel_on - 10e-3, relay_hold=t_rel_off - 210e-3)
    check(D, R)
    if plots:
        make_plots(D, R)
    R.pop("_switch_rows", None)
    json.dump(R, open(RESULTS, "w"), indent=1)
    report(D, R)


def check(D, R):
    """The analysis against the arithmetic: they must agree."""
    probs = []
    g_design = D["gain"]["total_hi"]
    ch = R["ac_hi"]["chain_gain"]
    filt = 10 ** (D["filter_db"][f"{D['site']['f_L']:.0f}"] / 20)
    if abs(ch / (g_design * filt) - 1) > 0.02:
        probs.append(f"chain gain {ch:.0f} vs the design's {g_design * filt:.0f}")
    q = R["ac_hi"]["q_tank"]
    if abs(q / D["coil"]["Q"] - 1) > 0.1:
        probs.append(f"tank Q {q:.1f} vs the coil's {D['coil']['Q']:.1f}")
    if abs(R["ac_hi"]["f_tank_peak"] / D["coil"]["dip_f"] - 1) > 0.01:
        probs.append(f"tank peak {R['ac_hi']['f_tank_peak']:.0f} Hz vs {D['coil']['dip_f']:.0f}")
    sq = R["sequencer"]
    if abs(sq["gate_delay"] / D["delay"]["t_gate"] - 1) > 0.15:
        probs.append(f"gate delay {sq['gate_delay'] * 1e3:.1f} ms vs {D['delay']['t_gate'] * 1e3:.1f}")
    if abs(sq["relay_hold"] / D["delay"]["t_hold"] - 1) > 0.15:
        probs.append(f"relay hold {sq['relay_hold'] * 1e3:.1f} ms vs {D['delay']['t_hold'] * 1e3:.1f}")
    so = R["switch_off"]
    if so["v_drain_peak"] > 190:
        probs.append(f"the drain reaches {so['v_drain_peak']:.0f} V: too near the IRFS4227's 200 V")
    if so["ramp_full"] > sq["relay_hold"]:
        probs.append("the coil's current outlasts the relay's hold")
    if probs:
        raise SystemExit("simulation and design disagree:\n  " + "\n  ".join(probs))


def report(D, R):
    a, n, so, sq = R["ac_hi"], R["noise"], R["switch_off"], R["sequencer"]
    print(f"  LISTEN: tank x{a['tank_per_emf']:.1f} over the coil's EMF at {D['site']['f_L']:.0f} Hz "
          f"(Q {a['q_tank']:.1f}, peak {a['f_tank_peak']:.0f} Hz); OUT x{R['ac_lo']['out_per_emf']:.0f} (LOW), "
          f"x{a['out_per_emf']:.0f} (HIGH) per volt of EMF")
    print(f"  60 Hz in the coil reaches OUT at x{a['out_60']:.2g} (HIGH); 180 Hz at x{a['out_180']:.2g}")
    print(f"  noise referred to the coil's EMF: {n['in_at_fL'] * 1e9:.2f} nV/rtHz at f_L "
          f"(the coil's own resistance: {n['coil_thermal'] * 1e9:.2f}); at OUT {n['out_at_fL'] * 1e6:.1f} uV/rtHz, "
          f"{n['out_rms_band'] * 1e3:.1f} mV rms 0.5-5 kHz")
    print(f"  FID at OUT (HIGH): {R['fid_out_hi']:.2f} V peak, single-shot SNR {R['snr_db']:.0f} dB in the tank's bandwidth")
    print(f"  CAL IN: 1 V at the generator gives {R['cal_lo_per_volt']:.2f} V at OUT on LOW")
    print(f"  switch-off at {so['i_on']:.2f} A ({so['v_supply']:.1f} V supply): drain peaks at {so['v_drain_peak']:.0f} V, "
          f"the current falls in {so['ramp_full'] * 1e3:.2f} ms, {so['e_tvs'] * 1e3:.0f} mJ into D7 "
          f"(the coil held {so['e_coil'] * 1e3:.0f} mJ)")
    print(f"  sequencer: GATE on {sq['gate_delay'] * 1e3:.1f} ms after POL CMD, off {sq['gate_off_lag'] * 1e6:.0f} us after; "
          f"RELAY on {sq['relay_on_lag'] * 1e6:.0f} us after, held {sq['relay_hold'] * 1e3:.1f} ms")


def make_plots(D, R):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(IMAGES, exist_ok=True)
    f = [r[0] for r in R["ac_curve"]]
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=130)
    ax.loglog(f, [r[1] for r in R["ac_curve"]], label="OUT / EMF in the coil (HIGH gain)", color="#1f5fbf")
    ax.loglog(f, [r[2] * 1000 for r in R["ac_curve"]], label="tank / EMF  x 1000", color="#c0392b")
    ax.axvline(D["site"]["f_L"], color="#888", lw=0.8, ls="--")
    ax.text(D["site"]["f_L"] * 1.05, 2, f"{D['site']['f_L']:.0f} Hz", color="#555", fontsize=8)
    for h in (60, 120, 180, 300):
        ax.axvline(h, color="#ddd", lw=0.6)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("gain (V / V)")
    ax.set_title("The receiver with the reference coil (sim/nmr_sim.py, from the netlist)", fontsize=9)
    ax.grid(True, which="both", lw=0.3, alpha=0.5)
    ax.legend(fontsize=8, loc="lower center")
    fig.tight_layout()
    fig.savefig(os.path.join(IMAGES, "sim_receiver.png"))
    plt.close(fig)
    rows = R["_switch_rows"]
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=130)
    t = [(r[0] - 41e-3) * 1e3 for r in rows]
    ax.plot(t, [r[1] for r in rows], color="#c0392b", label="DRAIN (V)")
    ax2 = ax.twinx()
    ax2.plot(t, [r[2] for r in rows], color="#1f5fbf", label="coil current (A)")
    ax.set_xlabel("time after the switch opens (ms)")
    ax.set_ylabel("DRAIN (V)", color="#c0392b")
    ax2.set_ylabel("current (A)", color="#1f5fbf")
    ax.set_title("Switch-off: D7 holds the drain, the current falls in a straight line", fontsize=9)
    ax.grid(True, lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(IMAGES, "sim_switch_off.png"))
    plt.close(fig)


if __name__ == "__main__":
    main(plots="--plots" in sys.argv)
