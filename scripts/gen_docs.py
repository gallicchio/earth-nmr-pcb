#!/usr/bin/env python3
"""Write the ordering documents, then check the hand-written ones.

Generated, from the parts table, the costed BOM, the board geometry and the
design arithmetic, so none of their numbers can drift from the files in out/:

    docs/MANUFACTURING.md                        what to upload, what to pick, what it costs
    out/earthnmr/earthnmr-fabrication-notes.txt  JLCPCB's order form, field by field
    out/earthnmr/PLACEMENT_CHECKS.txt            what to look at in JLCPCB's preview

Checked: the numbers README.md, docs/HANDBOOK.md and docs/DESIGN_NOTES.md
quote from the build are matched against the build (CLAIMS below), and the
build fails when a sentence no longer says what the files say.

(motor-pid's scripts/gen_docs.py, for a four-layer board with a relay.)
"""
import csv, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parts

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "out")
DOCS = os.path.join(ROOT, "docs")
STEM = "earthnmr"

# JLCPCB's prices are not on their parts API; these are estimates from their
# public price list, autumn 2026, for a four-layer 243 x 150 mm board, and the
# fab's own quote is the authority.  The build prints them only as an order of
# magnitude.
PCB_4L_5PCS = 55.00          # 5 pieces, 1.6 mm, green, HASL lead-free, JLC04161H-7628
PCB_4L_10PCS = 85.00
SHIPPING = 25.00             # DHL to the US
PCBA_SETUP = 25.00           # Standard PCBA: four layers and a D2PAK
STENCIL = 7.86
PER_JOINT = 0.0017
EXTENDED_PART_FEE = 3.00     # per distinct Extended code, not per placement
THT_SETUP = 3.58
THT_PER_JOINT = 0.03


def joint_counts():
    """Solder joints only: a mounting hole is not a joint."""
    geom = json.load(open(os.path.join(OUT, "pcb_geom.json")))
    real = [p for p in geom["pads"] if p["net"] and not p["ref"].startswith("MH")]
    smt = sum(1 for p in real if not p["through"])
    tht = sum(1 for p in real if p["through"])
    tht_refs = sorted({p["ref"] for p in real if p["through"]},
                      key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
    loops = len({p["ref"] for p in real if p["ref"].startswith("TP")})
    return smt, tht, tht_refs, loops, geom


def via_sizes():
    pcb = open(os.path.join(ROOT, "hardware", STEM + ".kicad_pcb")).read()
    vias = re.findall(r"\(via\s+\(at [^)]*\)\s+\(size ([0-9.]+)\)\s+\(drill ([0-9.]+)\)", pcb)
    return min(float(s) for s, d in vias), min(float(d) for s, d in vias), len(vias)


def bom_rows():
    return list(csv.DictReader(open(os.path.join(OUT, STEM, f"{STEM}_bom_costed.csv"))))


def money(x):
    return f"${x:,.2f}"


def circuit_check_count():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_circuit.py"),
                          os.path.join(OUT, STEM + ".net")], capture_output=True, text=True).stdout
    m = re.search(r"(\d+) circuit checks, 0 failed", out)
    return int(m.group(1)) if m else 0


def order_form(w, h, min_drill, min_via, tht_refs):
    """JLCPCB's order form, field by field in the order the web form shows them."""
    return [
        ("PCB", None, None),
        ("Base Material", "FR-4", "the default"),
        ("Layers", "4", "what the gerber set contains"),
        ("Dimensions", f"{w:.0f} x {h:.0f} mm", "read from the board outline"),
        ("PCB Qty", "5", "the minimum"),
        ("Product Type", "Industrial/Consumer electronics", "the default"),
        ("PCB Specifications", None, None),
        ("Different Design", "1", "one board in the outline"),
        ("Delivery Format", "Single PCB", "no panel"),
        ("PCB Thickness", "1.6 mm", "the BNC posts and the terminal blocks expect it"),
        ("PCB Color", "Green", "any; the white silkscreen is the schematic and reads best on green or black"),
        ("Silkscreen", "White", "the default for green"),
        ("Material Type", "FR4-Standard TG 135-140", "the default"),
        ("Impedance Control", "No", "nothing on this board is fast"),
        ("Layer Sequence", "F.Cu, In1.Cu, In2.Cu, B.Cu as named", "the gerbers name each layer"),
        ("Stackup", "JLC04161H-7628", "the stack-up the board file declares (1 oz outer, 0.5 oz inner)"),
        ("Surface Finish", "LeadFree HASL", "students handle this board: lead-free.  ENIG is fine too"),
        ("High-spec Options", None, None),
        ("Outer Copper Weight", "1 oz", "the default; the polarizing current's 2 mm tracks carry 3 A with 1 oz"),
        ("Inner Copper Weight", "0.5 oz", "the default"),
        ("Via Covering", "Tented", "or Plugged if the form upgrades it"),
        ("Min via hole size/diameter", "0.3 mm / (0.4 / 0.45 mm)" if min_drill >= 0.3 else "0.25 mm",
         f"the smallest via on the board is {min_drill:.2f} mm drill, {min_via:.2f} mm pad"),
        ("Board Outline Tolerance", "+/-0.2 mm (Regular)", "nothing mates with the edge"),
        ("Confirm Production file", "No", "the gerbers are checked here"),
        ("Mark on PCB", "Remove Mark", "the whole front is a drawing; nowhere for an order number"),
        ("Electrical Test", "Flying Probe Fully Test", "the default"),
        ("PCB Assembly", None, None),
        ("PCBA Type", "Standard", "four layers, a D2PAK and a relay; Economic if the form allows it for this board"),
        ("Assembly Side", "Top", "every part is on the front"),
        ("PCBA Qty", "2, or as many as the class needs", "the per-order fees are the same for 2 or 20"),
        ("Edge Rails/Fiducials", "Added by JLCPCB", "the board carries three fiducials"),
        ("Confirm Parts Placement", "Yes", "look at the preview against PLACEMENT_CHECKS.txt before paying"),
        ("Parts Selection", "By JLCPCB", "every BOM line has an LCSC code"),
        ("Through-hole parts", f"keep them: {', '.join(tht_refs)}",
         "the form lists them separately; the BNCs, terminals, relay, trimmers and film capacitors are meant to be fitted"),
        ("Bake Components", "No", "nothing moisture-sensitive"),
    ]


# What to look for in JLCPCB's preview, per orientation-sensitive part.
PREVIEW_CHECKS = [
    ("U1-U10", "the SOT-23-5's pin 1 dot", "at the upper right of each package, toward the triangle's point; pins 3 2 1 along the top"),
    ("U11", "the SOIC-8's pin 1 dot", "at the upper left"),
    ("Q1", "the D2PAK's tab", "up (toward the relay), the two leads down"),
    ("Q2, Q3, D12", "the SOT-23's lone pin", "up (the collector; D12's common)"),
    ("D1-D8, D10, D11, D13, D14", "each diode's cathode bar", "on the footprint's pad 1, the end the silkscreen bar marks"),
    ("D9", "the SMBJ12CA", "bidirectional: either way round"),
    ("LED1-LED4", "each LED's cathode mark", "on pad 1, the end the silkscreen marks"),
    ("C1, C2, C5", "the electrolytics' negative (striped) side", "on pad 2, away from the + mark"),
    ("K1", "the relay's pin 1", "the square pad, at the upper right of the two rows"),
    ("SW1", "the DIP's ON side", "facing down, toward pads 1-8 (the silkscreen says ON)"),
    ("SW2, SW3, SW4", "the slide switches' knob", "SW3 and SW2's knob down, SW4's up; their two posts key them"),
    ("RV1, RV2", "the trimmers' screw", "keyed by their holes; fits one way"),
    ("J1-J5, J7, J8", "the connectors' fronts", "off the board edge: J1 and J4 the top, J2 and J3 the left, J5 the right, J7 and J8 the bottom"),
    ("F1", "the PTC fuse", "not polarised"),
    ("TP1-TP21, TP100-TP103", "the test loops", "one pad each, either way"),
]


def expand_refs(text):
    """The designators a row names: "U1, U2" and "TP1-TP13" as a set."""
    out = set()
    for item in (i.strip() for i in text.split(",")):
        m = re.fullmatch(r"([A-Z]+)(\d+)-\1?(\d+)", item)
        if m:
            out |= {f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)}
        elif item:
            out.add(item)
    return out


def main():
    rows = bom_rows()
    smt, tht, tht_refs, loops, geom = joint_counts()
    min_via, min_drill, n_vias = via_sizes()
    D = json.load(open(os.path.join(ROOT, "sim", "design.json")))
    R = json.load(open(os.path.join(ROOT, "sim", "results.json")))
    parts_cost = sum(float(r["Ext $"]) for r in rows)
    ext_codes = sorted({r["LCSC Part #"] for r in rows if r["JLC"] == "extended"})
    ext_fee = EXTENDED_PART_FEE * len(ext_codes)
    w, h = geom["board_w"], geom["board_h"]
    ref_lcsc = {}
    for r in rows:
        for ref in r["Designator"].split(","):
            ref_lcsc[ref.strip()] = r["LCSC Part #"].strip()
    nchecks = circuit_check_count()

    def quote(qty, pcb_cost):
        parts_total = parts_cost * qty
        assembly = (PCBA_SETUP + STENCIL + ext_fee + THT_SETUP + PER_JOINT * smt * qty + THT_PER_JOINT * tht * qty)
        return pcb_cost, parts_total, assembly, SHIPPING, pcb_cost + parts_total + assembly + SHIPPING

    form = order_form(w, h, min_drill, min_via, tht_refs)

    L = []
    a = L.append
    a("# Manufacturing")
    a("")
    a("*Generated by `scripts/gen_docs.py` from the costed BOM, the board file and the parts table: edit those, not this.*")
    a("")
    a(f"One board, four layers, {w:.0f} x {h:.0f} mm, every part on the top side: ground on")
    a("the second layer, +15 V on the third, -15 V on the back with the three hops.  It passes ERC,")
    a(f"DRC at every severity with schematic parity, the {nchecks} circuit assertions on the netlist,")
    a("the simulation's agreement with the design arithmetic and the fab-package checks, and")
    a("`./make.py` rebuilds and rechecks everything from scratch in about a minute and a half.")
    a("")
    a("## What to upload")
    a("")
    a("| file | where it goes |")
    a("|---|---|")
    a(f"| `out/{STEM}/{STEM}-gerbers.zip` | the *Add gerber file* box |")
    a(f"| `out/{STEM}/{STEM}_bom_jlcpcb_upload.csv` | the BOM box (JLCPCB's column layout) |")
    a(f"| **`out/{STEM}/{STEM}_cpl_jlcpcb_upload.csv`** | the CPL / pick-and-place box, at JLCPCB |")
    a(f"| `out/{STEM}/{STEM}_cpl_kicad_native.csv` | the CPL box at any other fab |")
    a(f"| `out/{STEM}/{STEM}-assembly-notes.txt` | paste into the assembly remark |")
    a("")
    a("## The order form, field by field")
    a("")
    a(f"The same list is in `out/{STEM}/{STEM}-fabrication-notes.txt` to keep open while ordering.")
    a("")
    a("| field | pick | why |")
    a("|---|---|---|")
    for field, value, why in form:
        a(f"| **{field}** | | |" if value is None else f"| {field} | {value} | {why} |")
    a("")
    a("## Cost")
    a("")
    a(f"The board has **{smt} SMT joints** and **{tht} through-hole joints** on {len(rows)} BOM lines;")
    a(f"{len(ext_codes)} distinct order codes are JLCPCB *Extended* parts, each with a one-off")
    a(f"{money(EXTENDED_PART_FEE)} feeder fee.  Parts alone are **{money(parts_cost)} per board**, of which the")
    a(f"four BNC jacks are {money(4 * parts.PARTS['BNC']['price'])}, the relay {money(parts.PARTS['RELAY']['price'])}"
      f" and the {loops} test loops {money(loops * parts.PARTS['TP']['price'])}.")
    a("")
    a("The bare-board and assembly lines below are estimates from JLCPCB's public price list for a")
    a(f"four-layer {w:.0f} x {h:.0f} mm board, not a quote: their order page is the authority.")
    a("")
    for qty, pcb in ((2, PCB_4L_5PCS), (5, PCB_4L_5PCS), (10, PCB_4L_10PCS)):
        p, pr, asm, ship, tot = quote(qty, pcb)
        a(f"**{qty} boards, fully assembled, through-hole parts included**")
        a("")
        a("| line | cost |")
        a("|---|---|")
        a(f"| bare PCBs ({max(qty, 5)} made) | about {money(p)} |")
        a(f"| parts ({money(parts_cost)} x {qty}) | {money(pr)} |")
        a(f"| assembly: setup + stencil + THT setup + {len(ext_codes)} extended codes + {smt * qty} SMT and "
          f"{tht * qty} THT joints | about {money(asm)} |")
        a(f"| shipping (DHL) | about {money(ship)} |")
        a(f"| **total** | **about {money(tot)}**  ({money(tot / qty)} each) |")
        a("")
    a("The coil, its former, the water bottle and the polarizing supply are not on the order; the")
    a("[handbook](HANDBOOK.md) lists them.")
    a("")
    a("## Rotations JLCPCB needs")
    a("")
    a("JLCPCB places from its own drawing of each part, and for some parts that drawing is turned")
    a("from KiCad's footprint.  The upload CPL has these angles applied, per LCSC code, from")
    a("`scripts/parts.py` `JLC_ROTATION`:")
    a("")
    a("| parts | LCSC | turned by | datum shift | evidence |")
    a("|---|---|---|---|---|")
    for code, (deg, (dx, dy), how, note) in sorted(parts.JLC_ROTATION.items(), key=lambda kv: (-kv[1][0], kv[0])):
        refs = sorted((r for r, c in ref_lcsc.items() if c == code),
                      key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
        if not refs:
            continue
        shift = f"({dx:+.2f}, {dy:+.2f}) mm" if (dx or dy) else "none"
        a(f"| {', '.join(refs)} | {code} | {deg} deg | {shift} | {how}: {note} |")
    a("")
    a("*read* means seen in a JLCPCB preview on a real order of that part on that footprint (on one")
    a("of the other boards); *predicted* means derived by fitting JLCPCB's own land pattern onto ours")
    a("by pin number (`scripts/check_rotations.py`).  Every part not listed goes at KiCad's angle.")
    a(f"`out/{STEM}/PLACEMENT_CHECKS.txt` is the list to hold against the preview.  After adding or")
    a("changing a part, run `scripts/check_rotations.py` and `scripts/check_pinouts.py` (they need the")
    a("network, so the build does not run them).  `check_outputs.py` proves the two CPL files differ in")
    a("nothing but those angles.")
    a("")
    a("## Check these in the preview before you pay")
    a("")
    a("| part | what to look for | should be |")
    a("|---|---|---|")
    for line in PREVIEW_CHECKS:
        a(f"| {line[0]} | {line[1]} | {line[2]} |")
    a("")
    a("The parts that cannot go in wrong are the relay and the two trimmers: their hole patterns fit")
    a("one way, and `check_outputs.py` re-derives that from the board file on every build.")
    a("")
    a("## The through-hole parts")
    a("")
    a(f"{len(tht_refs)} parts are through-hole: **{', '.join(tht_refs)}**: the four BNC jacks, the three")
    a("terminal blocks, the relay, the two trimmers and the three film capacitors.  They are in the BOM")
    a("and the CPL and JLCPCB fits them for a per-order fee plus pennies a joint; keep them selected")
    a(f"when the form lists them.  Soldered by hand they are the {tht} largest joints on the board.")
    a("")
    a("## Parts, stock and alternates")
    a("")
    a(f"Stock as JLCPCB's parts API reported it on {parts.STOCK_DATE}; the build re-reads every code's")
    a("description against the value and package here and stops if one has changed or run out.")
    a("")
    a("| ref | value | LCSC | JLC | unit | stock then | notes |")
    a("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (re.sub(r"\d", "", r["Designator"].split(",")[0]),
                                         int(re.sub(r"\D", "", r["Designator"].split(",")[0]) or 0))):
        key = next((k for k, p in parts.PARTS.items() if p.get("lcsc") == r["LCSC Part #"]), None)
        p = parts.PARTS.get(key, {})
        if p:
            stock, note = p.get("stock", ""), p.get("desc", "")
        else:
            pv = next((v for v in parts.PASSIVES.values() if v["lcsc"] == r["LCSC Part #"]), {})
            stock, note = pv.get("stock", ""), pv.get("note", "")
        stock_s = f"{stock:,}" if isinstance(stock, int) else str(stock)
        note = " ".join(str(note).split())
        a(f"| {r['Designator']} | {r['Comment']} | {r['LCSC Part #']} | {r['JLC']} | ${r['Unit $']} | {stock_s} | {note} |")
    a("")
    a("### If something is out of stock")
    a("")
    for key, p in parts.PARTS.items():
        for alt in p.get("alt", []):
            a(f"- **{p['mpn']}** ({p['lcsc']}): {alt}")
    a("")
    per_board = {}
    for r in rows:
        per_board[r["LCSC Part #"]] = per_board.get(r["LCSC Part #"], 0) + len(r["Designator"].split(","))
    worth = sorted((p["stock"] // per_board[p["lcsc"]], p["mpn"], p["stock"], per_board[p["lcsc"]])
                   for p in list(parts.PARTS.values()) + list(parts.PASSIVES.values())
                   if p.get("lcsc") in per_board and isinstance(p.get("stock"), int))
    a(f"The thinnest line is the {worth[0][1]}: {worth[0][2]:,} in stock and {worth[0][3]} per board, about")
    a(f"{worth[0][0]:,} boards' worth; next the {worth[1][1]} at about {worth[1][0]:,}.")
    a("")
    a("## After the boards arrive")
    a("")
    a("The bring-up order, the expected voltage at every loop and the experiments are in")
    a("[HANDBOOK.md](HANDBOOK.md).  In one line: with no coil and no polarizing supply, power it at")
    a("+-15 V, both green lamps light, MODE at LISTEN, and a 1 V sine at CAL IN at the tank's")
    a("frequency shows at OUT; then the coil, then RUN.")
    a("")
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "MANUFACTURING.md")
    open(path, "w").write("\n".join(L) + "\n")
    print(f"  wrote {os.path.relpath(path, ROOT)} (parts {money(parts_cost)}/board, "
          f"{smt} SMT + {tht} THT joints, {len(ext_codes)} extended codes)")

    N = [f"{parts.BOARD_NAME} rev {parts.REV} ({parts.BOARD_DATE}) -- JLCPCB order form, field by field", "=" * 78, ""]
    for field, value, why in form:
        N.append(f"[{field}]" if value is None else f"  {field:28s} {value}" + (f"      ({why})" if why else ""))
    N += ["", "Upload:", f"  gerbers     out/{STEM}/{STEM}-gerbers.zip",
          f"  BOM         out/{STEM}/{STEM}_bom_jlcpcb_upload.csv",
          f"  CPL         out/{STEM}/{STEM}_cpl_jlcpcb_upload.csv   (JLCPCB only; others take _kicad_native)",
          f"  remark      paste out/{STEM}/{STEM}-assembly-notes.txt",
          "", "Then read PLACEMENT_CHECKS.txt against the preview, front and (empty) back."]
    path = os.path.join(OUT, STEM, f"{STEM}-fabrication-notes.txt")
    open(path, "w").write("\n".join(N) + "\n")
    print(f"  wrote {os.path.relpath(path, ROOT)}")

    P = [f"PLACEMENT CHECKS for {parts.BOARD_NAME} rev {parts.REV}: JLCPCB's 'Confirm Parts Placement' preview",
         "=" * 78, "",
         "The upload CPL turns some parts by the angle JLCPCB's own drawing needs.  'read' angles were",
         "seen in a real preview of the same part (on another of Jason's boards); 'predicted' ones come",
         "from fitting JLCPCB's land pattern on ours.  If a part is turned in the preview, do NOT nudge",
         "it in their viewer (the fix is lost on the next upload): change its entry in scripts/parts.py",
         "JLC_ROTATION and rebuild.", "", "Every orientation-sensitive part, and what it should look like:", ""]
    for refs, what, should in PREVIEW_CHECKS:
        codes = sorted({ref_lcsc.get(r, "") for r in expand_refs(refs)} - {""})
        turns = [f"{c} +{parts.JLC_ROTATION[c][0]} deg ({parts.JLC_ROTATION[c][2]})" for c in codes if c in parts.JLC_ROTATION]
        P.append(f"  {refs}: {what}; should be: {should}")
        if turns:
            P.append(f"      upload turns: {', '.join(turns)}")
    P += ["", "Symmetric parts (every resistor and ceramic capacitor) cannot go in wrong.",
          "The back of the board carries no parts: check it anyway, it should be empty.", ""]
    missing = set(ref_lcsc) - set().union(*(expand_refs(r) for r, _, _ in PREVIEW_CHECKS))
    polar = {r for r in missing if not re.match(r"^(R|C)\d", r) or r in ("C1", "C2", "C5")}
    if polar:
        raise SystemExit("PLACEMENT_CHECKS: no preview row names " + ", ".join(sorted(polar)))
    path = os.path.join(OUT, STEM, "PLACEMENT_CHECKS.txt")
    open(path, "w").write("\n".join(P) + "\n")
    print(f"  wrote {os.path.relpath(path, ROOT)}")

    bad, n = [], 0
    for rel, pat, want in CLAIMS(D, R, nchecks, parts_cost, w, h):
        if not os.path.exists(os.path.join(ROOT, rel)):
            bad.append(f"{rel}: missing")
            continue
        text = re.sub(r"\s+", " ", open(os.path.join(ROOT, rel)).read())
        n += 1
        m = re.search(pat, text)
        if not m:
            bad.append(f"{rel}: no sentence matches /{pat}/")
            continue
        got = m.groups() if isinstance(want, tuple) else m.group(1)
        if got != want:
            bad.append(f"{rel}: says {got!r}, the build says {want!r}  (/{pat}/)")
    for b in bad:
        print(f"  STALE {b}")
    print(f"  {n - len(bad)} of {n} document claims match the build")
    return 1 if bad else 0


def CLAIMS(D, R, nchecks, parts_cost, w, h):
    """(file, regex with one group or several, the build's value or tuple of values)."""
    c, site = D["coil"], D["site"]
    fL = f"{site['f_L']:.0f}"
    out = []
    for rel in ("README.md", "docs/HANDBOOK.md"):
        out.append((rel, r"Larmor frequency[^.]*? (\d{4}) Hz", fL))
    out += [
        ("README.md", r"(\d+) circuit assertions", str(nchecks)),
        ("README.md", r"(\d+) x (\d+) mm, four layers", (f"{w:.0f}", f"{h:.0f}")),
        ("README.md", r"parts come to about \$(\d+) a board", f"{parts_cost:.0f}"),
        ("README.md", r"x(\d+) \(LOW\) or x(\d+) \(HIGH\)", (f"{D['gain']['total_lo']:.0f}", f"{D['gain']['total_hi']:.0f}")),
        ("docs/HANDBOOK.md", r"(\d+) turns of AWG 20", str(c["N"])),
        ("docs/HANDBOOK.md", r"about (\d+\.\d) mH and (\d+\.\d) ohm", (f"{c['L'] * 1e3:.1f}", f"{c['R']:.1f}")),
        ("docs/HANDBOOK.md", r"switches ([1-8 ]+) ON for", " ".join(str(i + 1) for i in range(8) if c["dip_code"] >> i & 1)),
        ("docs/HANDBOOK.md", r"peaks near (\d+) V", f"{R['switch_off']['v_drain_peak']:.0f}"),
        ("docs/HANDBOOK.md", r"GATE (\d+) ms after", f"{D['delay']['t_gate'] * 1e3:.0f}"),
        ("docs/DESIGN_NOTES.md", r"(\d\.\d) A from a (\d+) V supply", (f"{c['I_pol']:.1f}", f"{c['V_pol']:.0f}")),
        ("docs/DESIGN_NOTES.md", r"single-shot SNR of about (\d+) dB", f"{R['snr_db']:.0f}"),
    ]
    return out


if __name__ == "__main__":
    sys.exit(main())
