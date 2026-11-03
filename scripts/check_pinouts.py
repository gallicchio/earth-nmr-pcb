#!/usr/bin/env python3
"""Does each part's symbol name its pins as the maker does?  For every part with an LCSC code, compare the pin names
on our schematic symbol (the one embedded in hardware/earthnmr.kicad_sch) with the names on EasyEDA's symbol for the
same code (scripts/easyeda.py: the drawing JLCPCB's catalogue shows, usually copied from the datasheet), pin number
by pin number.

    python3 scripts/check_pinouts.py

AMOD-and-RFMOD's check_pinouts.py (CLAUDE_PCB.md section 26), with the polarised two-pin parts kept (a diode's K and
A, an electrolytic's + and -): on this board they are where a pin-number mistake would hurt.  A pin-number fit
(check_rotations.py) cannot see a symbol that carries another part's pinout.  Names are compared after normalising
(case, punctuation, the usual synonyms); a part whose names disagree is printed side by side for a person to read
against the datasheet.  Like check_rotations.py it needs the network the first time, so ./make.py does not run it.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import parts, easyeda
from sexp_parse import parse_file

STEM = "earthnmr"
UNPOLAR = ("Device:R", "Device:C", "Device:Polyfuse", "Connector:TestPoint", "Mechanical:")
# differences read against the datasheet and the placement: the table is right
KNOWN = {
    "C2297": "KT-0805G: JLCPCB numbers its anode 1; their pad 1 lies on our pad 2 (A), so at 0 their cathode is on ours "
             "(check_rotations.py, the upload; read at 0 in GPiBridge's preview)",
}
SYN = [("VCC", "VDD", "V+", "VS+", "+VS", "VPOS", "VP", "VCC+"),
       ("GND", "VSS", "V-", "VS-", "-VS", "VEE", "VNEG", "VCC-"),
       ("+IN", "IN+", "INP", "+", "NONINV", "IN_P", "VIN+", "INPUT+"), ("-IN", "IN-", "INN", "-", "INV", "IN_N", "VIN-", "INPUT-"),
       ("OUT", "OUTPUT", "VOUT"), ("K", "CATHODE", "C-", "KATHODE"), ("A", "ANODE", "A+"),
       ("COM", "COMMON", "AK", "KA", "K1/A2", "A2/K1"),
       ("B", "BASE"), ("C", "COLLECTOR"), ("E", "EMITTER")]


def norm(name, diode=False):
    n = re.sub(r"[~{}\s_/^#]", "", (name or "").upper()).replace("OVERLINE", "")
    if diode and n in ("+", "-"):
        return "A" if n == "+" else "K"                  # an LED drawn with + and -
    if diode and n == "C":
        return "K"                                       # a TVS's cathode named C
    for group in SYN:
        if n in [re.sub(r"[\s_/]", "", g) for g in group]:
            return group[0]
    return n


def our_symbols():
    """{lib_id: {number: name}} from the schematic's embedded library."""
    root = parse_file(os.path.join(ROOT, "hardware", STEM + ".kicad_sch"))
    out = {}
    for sym in root.first("lib_symbols").kids("symbol"):
        pins, stack = {}, [sym]
        while stack:
            n = stack.pop()
            for k in n.kids():
                if k.tag == "pin":
                    pins[k.first("number").atom(0)] = k.first("name").atom(0)
                else:
                    stack.append(k)
        out[sym.atom(0)] = pins
    return out


def their_pins(code):
    """{number: name} from EasyEDA's symbol: its pin-number and pin-name texts, paired by the pin each belongs to."""
    res, _ = easyeda.svgs(code)
    sym = next((r for r in (res or []) if isinstance(r, dict) and r.get("docType") == 2), None)
    if not sym:
        return {}
    out = {}
    for g in re.finditer(r'<g c_partid="part_pin"([^>]*)>(.*?)</g>', sym["svg"], re.S):
        num = re.search(r'c_spicepin="([^"]*)"', g.group(1))
        if not num:
            continue
        texts = [t.strip() for t in re.findall(r'<text[^>]*>([^<]*)</text>', g.group(2))]
        names = [t for t in texts if t and t != num.group(1)]
        out[num.group(1)] = names[0] if names else ""
    return out


def main():
    ours, seen, bad = our_symbols(), set(), 0
    for key, p in list(parts.PARTS.items()) + list(parts.PASSIVES.items()):
        lcsc, sym = p.get("lcsc"), p.get("symbol", "")
        if not lcsc or (lcsc, sym) in seen or (sym.startswith(UNPOLAR) and not sym.startswith("Device:C_Polarized")):
            continue
        mine = next((v for k, v in ours.items() if k == sym or k.endswith(":" + sym.split(":")[-1])), None)
        if mine is None or len(mine) < 2:
            continue
        seen.add((lcsc, sym))
        try:
            theirs = their_pins(lcsc)
        except Exception as e:  # noqa
            print("  ?       %-10s %-10s %s" % (lcsc, key, e))
            continue
        if not theirs or not any(theirs.values()):
            print("  ?       %-10s %-10s EasyEDA's symbol has no pin names (numbers only): %s" % (lcsc, key, theirs))
            continue
        diode = sym.startswith(("Device:D", "Device:LED"))
        # KiCad leaves some pins unnamed ("~", an op-amp's output): nothing to compare
        diff = [n for n in mine if n in theirs and norm(mine[n]) and norm(mine[n], diode) != norm(theirs[n], diode)]
        flag = "ok" if not diff else ("known" if lcsc in KNOWN else "DIFFERS")
        bad += flag == "DIFFERS"
        print("  %-7s %-10s %-10s %-34s (%d of %d pins compared)%s" % (flag, lcsc, key, sym, len([n for n in mine if n in theirs]),
                                                                   len(mine), ("\n            " + KNOWN[lcsc]) if flag == "known" else ""))
        for n in sorted(mine, key=lambda s: (len(s), s)):
            print("            pin %-3s ours %-8s theirs %-12s %s" % (n, mine[n], theirs.get(n, "-"), "<<" if n in diff else ""))
    print("\n%d part(s) whose pin names differ from EasyEDA's: read each against its datasheet" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
