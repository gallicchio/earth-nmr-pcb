# Claude Code Chat Log — Earth's Field NMR

Every prompt, verbatim, followed by the response as it was given, with the renders as
they were at the time (kept under `docs/history/`).  Claude, in a Claude Code cloud
session.

## Prompt 1

> Design an Earth NMR circuit and PCB like my other PCBs on github. Write only to earth-nmr-pcb, but look at the other repos, especially in OpticsPCBs, where there is a CLAUDE_PCB.md that you should follow. Install kicad 10 in your cloud environment.

## Response 1

*2026-11-01 17:04 PST (01:04 UTC 2026-11-02) to 2026-11-01 20:00 PST (04:00 UTC), one sitting.*

### What was built

KiCad 10.0.8 installed in the cloud container from the KiCad 10.0 PPA (its
`add-apt-repository` needs a Python module the container's Python 3.13 lacks, so the
key and source list went in by hand; `pcbnew` is built for `/usr/bin/python3`, 3.12,
and `scripts/kienv.py` now finds a Python that can import it).  Then a complete,
script-generated project in the style of `motor-pid` and `op-amp-pcb`, following
`OpticsPCBs/CLAUDE_PCB.md`:

- `scripts/parts.py` — the parts table: every part JLCPCB-stocked, with its LCSC code,
  price and stock on 2026-11-02, footprint, and the per-code JLCPCB rotation table.
- `sim/design.py` → `sim/design.json` — the arithmetic, once: the site's field (IGRF-14
  via `ppigrf` for Harvey Mudd: 46,028 nT, 1959.8 Hz), the coil, the polarizing field
  and current, the signal and the noise, the bank, every filter, the gains, the
  sequencer's times, the switch-off.  Everything printed on the sheet and the board reads
  from it.
- `scripts/gen_symbols.py`, `gen_footprints.py`, `gen_models.py` — the TS391 and HFD3
  symbols (pins checked against the datasheets), the BNC, terminal, trimmer, slide switch,
  DIP switch, film capacitor and test loop footprints, and plain 3D stand-ins.
- `scripts/gen_sch.py` — the A1 sheet; ERC 0, no text overlaps (`check_schematic.py`).
- `scripts/check_circuit.py` — 365 assertions on the exported netlist: every net written
  out, every value, the C0G parts, polarities, the bypassing.
- `sim/nmr_sim.py` — ngspice on the exported netlist: the tank, the receiver's gain, band,
  60/180 Hz rejection and noise, the CAL response, the switch-off, the sequencer; each
  checked against the arithmetic.
- `scripts/layout.py` + `scripts/gen_pcb.py` — the 243 x 150 mm, four-layer board: every
  drawn wire laid as copper and as silkscreen, planes for ground, +15 V and -15 V with a
  via and a mark at every pad on them, three hops; DRC 0 at every severity with
  schematic parity.
- `scripts/gen_outputs.py`, `check_outputs.py`, `gen_docs.py` — gerbers, drill, BOM,
  CPL (native and JLCPCB-corrected), assembly drawings, renders, STEP; the fab checks (QR
  decoded back off the board, keyed parts, 3D models, every LCSC code against JLCPCB's
  own description and stock); the generated `docs/MANUFACTURING.md`, order form and
  `PLACEMENT_CHECKS.txt`; the claims check on the hand-written documents.
- `make.py` — all of it in one command, about 70 seconds; a second run changes no committed file
  (the tilted 3D view, which KiCad renders a little differently each time, goes to `build/`).
- `README.md`, `docs/HANDBOOK.md`, `docs/DESIGN_NOTES.md`, this log.

![the board](docs/history/r1-render-top.png)

![the front, copper and silkscreen](docs/history/r1-top.png)

![the schematic](docs/history/r1-schematic.png)

### How it works

Polarize a litre of water with 1.5 A in a 916-turn coil (7.8 mT, 170 times the Earth's
field); switch the current off in 0.4 ms, much faster than the protons can follow; let
the relay hand the coil to a tank tuned to 1960 Hz; amplify the 1.2 µV the precessing
protons induce (45 µV across the tank) by 2121 or 20301 through an instrumentation
amplifier and a 688 Hz-4.2 kHz band-pass; repeat on a 555's timing.

### Decisions, and why

| decision | why |
|---|---|
| one coil, polarizing and receiving, handed over by a DPDT relay | the classic Earth's-field design; two coils would couple anyway |
| the relay never switches current: it closes 18 ms before Q1 turns on, opens 15 ms after Q1 turns off | a 3 A signal relay with gold-flashed contacts can carry the polarizing current and the microvolt signal if it never makes or breaks either |
| Q1 IRFS4227 (200 V) with an SMCJ100A clamp, drain to source | the coil's 30 mJ goes into a part made for it, at a constant ~127 V, so the current falls in a straight line: fast where it matters (7 µs through the Earth's-field region against a 500 µs Larmor period), the non-adiabatic switch-off the measurement needs |
| polarizing supply separate from ±15 V, 6-30 V, up to 3 A | 20 W for seconds; a battery is the quietest source; its return stays off the receiver's side of the plane |
| eight-switch DIP with binary C0G columns, 3.3 nF steps to 841 nF | tunes the coil anywhere on Earth (937-2853 Hz) in 13 Hz steps, no trimmer to drift |
| three-op-amp INA, OPA197 | the tank's own 14 nV/rtHz dominates: the receiver adds 1.7 dB; differential input rejects the cable's common mode |
| fourth-order high-pass at 688 Hz, second-order low-pass at 4.2 kHz | 60 Hz -85 dB, 180 Hz -47 dB, the relay's step gone; the world's Larmor range within 0.9 dB |
| gain x21 or x201 after the filters | 0.8 V of FID at OUT on HIGH for a litre of water; LOW for a bigger sample |
| NE555 astable with diode-steered charge and discharge | POLARIZE TIME and LISTEN TIME independent, 0.2-4.7 s each |
| two TS391 comparators on RC delays from POL CMD | the relay-first, relay-last order in four parts each, no logic |
| POLARIZE IN (a 1.3 V comparator with hysteresis) and SYNC OUT | a computer or generator can run the sequence; a scope or sound card triggers on it |
| CAL IN through 1M | a known current into the tank, to tune it without protons |
| four layers: ground, +15 V, -15 V planes | the rails need no drawing on a board whose wires are all drawn; every IC's bypass hangs from its own via |
| the coil's two leads close a loop round the polarizing switch | the 3 A path needs no hop; GATE dives under the loop instead |
| the audio jack dropped | the PJ-320D's tip/ring/sleeve pinout could not be confirmed from its datasheet; OUT's BNC and a lead do the job |
| J3: shield on top, A, B | the floorplan: the coil's leads reach the relay's commons without crossing |
| SW3's throws: 1 EXT, 3 INT | the switch's common between its two sources on the board |

### Found along the way

- **The 47 nF C0G of tuning column 5 had sold out** (C20617849, 0 in stock on
  2026-11-02, found by `check_outputs.py`'s stock check): Holy Stone's C1206N473J050T
  (C5451690, 1248 in stock, 50 V) instead.
- **The MSK12C02's 3D model was 2.54 times too big**: `gen_footprints.py` gave it no
  1/2.54 scale, so the slide switches rendered as 17 mm blocks.  Fixed here.  The same
  line is in motor-pid's `scripts/gen_footprints.py` (its switches render the same way);
  this session writes only to this repository, so it is left for motor-pid.
- **The transistor symbol's base hairline crossed its own pad** (`q_geometry`, from
  motor-pid): it started from the pad's far edge.  It now leaves the edge facing the bar.
- **The BNC jacks are the thinnest stock**: 215 on JLCPCB's shelf, four per board.
- **Five parts would have been placed wrong at KiCad's angles**: `check_rotations.py`
  (from motor-pid, fed JLCPCB's own land patterns) found the relay turned a quarter with
  its origin in the middle of its pins, the 555 a quarter, the BAV99 and MMBT3904 half
  a turn, the D2PAK's origin 2.56 mm along; and the terminal blocks' bodies backwards
  (as the op-amp board's preview showed).  All are in `parts.JLC_ROTATION` now and the
  check passes: every pad of theirs within 0.3 mm of ours but D9's (0.44, an SMB drawn
  larger), every body inside our courtyard.
- **`check_pinouts.py`** compares our symbols with JLCPCB's: the TS391, OPA197, NE555,
  MMBT3904, the MOSFET and the diodes agree pin for pin (it needed "VCC-"/"VCC+" and a
  TVS's "C" for cathode as synonyms); the relay, BAV99, DIP and connectors have numbers
  only there.

### What would most likely make the first board dead on arrival

| risk | how likely | what shows it, what rescues it |
|---|---|---|
| the HFD3's pinout (as the G6S-2) | the likeliest: a symbol split here, JLCPCB's symbol has numbers only | JLCPCB's land pattern matches ours hole for hole; with the relay at rest, TANK+ to TANK- reads the coil's 9 ohm |
| TS391's pinout (custom symbol, 1 OUT 2 V- 3 IN- 4 IN+ 5 V+) | low: JLCPCB's symbol agrees pin for pin (`check_pinouts.py`) | bring-up 5.2: GATE and RELAY in the wrong order |
| the switch-off rings harder than simulated (the coil's own capacitance) | moderate | DRAIN on a x10 probe, first at 6 V polarizing; D7 limits it in any case |
| the polarizing current's return upsets the receiver | low: it flows only while the receiver is disconnected | the 19 ms before the relay hands over; a heavier ground return in rev B |
| the DIP switch's ON side, the slide switches' sense | low | the silkscreen's words; read them inverted |
| a JLCPCB placement turned | low: `check_rotations.py` fitted JLCPCB's own drawing of every part; the relay (+270, shifted), 555 (+270), SOT-23s (+180) and D2PAK (shifted) were wrong at KiCad's angle and are corrected; the MMBT3904 and terminal blocks were read on the op-amp board | `PLACEMENT_CHECKS.txt` against the preview |

### Not done

- No outside design review yet (CLAUDE_PCB.md: a brief for other LLMs under
  `design_reviews/` when the board is ready); the board is rev A, not ordered.
- Not built, so nothing here is measured: every number is arithmetic or simulation.

## Prompt 2

> I want an audio jack for a standard 3.5mm headphones. Find one with a known pinout on JLCPCB. Also, fix the small issue in motor-pid if you can confirm your improvement.

## Response 2

*2026-11-01 20:12 PST (04:12 UTC 2026-11-02) to 21:08 PST (05:08 UTC), one sitting.*

### What was added

A **HEADPHONES** block in the bottom right corner, under GAIN: OUT through R58 (62k) onto a
VOLUME knob (RV3, 10k, clockwise louder), U12 (an OPA197 follower), and 100 ohm from it to the
tip (R56) and to the ring (R57) of J9, a 3.5 mm stereo jack at the right edge, next to OUT's
BNC.  Both ears get the same signal.  Full volume puts x0.034 of OUT into a 32 ohm earpiece:
the 0.8 V FID on HIGH is 30 mV in the ear, about 81 dB SPL in a 100 dB/mW earpiece, a clear
whistle at 1960 Hz.  The simulation of the netlist (the knob fully clockwise, 32 ohm in each
ear) gives x0.0337, the arithmetic's number.  A PHONES probe loop (TP22) is on U12's output.

![the board](docs/history/r2-render-top.png)

![the front, copper and silkscreen](docs/history/r2-top.png)

![the schematic](docs/history/r2-schematic.png)

### The jack, and how its pinout is known

**Same Sky (formerly CUI) SJ1-3523N, LCSC C20182914**: through-hole, right angle, three pins, no
switches; 353 on JLCPCB's shelf, $1.23.  JLCPCB has no datasheet for it, so the maker's
(`sj1-352xn.pdf`, 09/12/2024) was read: **1 sleeve, 2 tip, 3 ring**, the plug's sections
numbered to match.  Three sources agree on where those pins are:

| source | what it says |
|---|---|
| Same Sky's drawing | the sleeve on the centre line about 3.5 mm in from the board's edge, the tip and the ring 5 mm either side of it and 5 mm further in |
| KiCad's footprint (`Connector_Audio:Jack_3.5mm_CUI_SJ1-3523N_Horizontal`) | pads S, T and R in exactly those places |
| JLCPCB's land pattern (EasyEDA, numbered 1-3) | lies on ours at 0.00 mm, pegs and pins, with 1 = S, 2 = T, 3 = R (`check_rotations.py`, which now takes such a map) |

EasyEDA's symbol for it carries pin numbers only (`check_pinouts.py`), so the names rest on the
maker's table, which the two drawings confirm.  Both ears carry the same signal, so a tip and
ring swapped would not matter; the sleeve is what must be right, and it is the lone pin.

### Decisions, and why

| decision | why |
|---|---|
| SJ1-3523N | of the stocked jacks looked at, the one whose maker's table, KiCad footprint and JLCPCB's numbered land pattern all exist and agree |
| not SJ1-3533NG (C4992459) | EasyEDA has no land pattern for it and KiCad no model: nothing to check its pins against |
| not SJ-3524-SMT-TR (C20182907) | the same jack in surface mount; kept as the alternate |
| the PJ-320D (rev A's draft) stays out | its datasheet gives no pin roles |
| VOLUME: ALPS RK09K 10k, 20 mm flat shaft (C202373) | motor-pid's knob without its centre detent; its footprint, 3D model and JLCPCB placement already worked out there |
| 62k ahead of the knob | full volume is x0.139 of OUT: 81 dB SPL for the FID; OUT at a rail (the relay's hand-over) would be 106 dB, so the handbook says start low |
| an OPA197 follower, 100 ohm per ear | the receiver's op-amp; drives 32 ohm; stable into a cable; a mono plug (ring to sleeve) draws 21 mA, 42 mW in an 0805 |
| both ears the same | the FID is mono |
| J9 at the right edge, below OUT | the audio leaves the board beside OUT's BNC; the block fits under GAIN |

### Found along the way

- **KiCad's SJ1-3523N footprint excludes itself from the BOM and the placement file and draws an
  edge notch on Edge.Cuts**: DRC reported the parity mismatch and an invalid outline.
  `gen_pcb.py` now clears both exclusions on every fitted part and removes any footprint's
  Edge.Cuts, and the jack's silkscreen past the board's edge.
- **JLCPCB's placements**: the jack's drawing is KiCad's turned 180, its origin 2.5 mm from the
  sleeve toward the tip and ring; the knob's is turned 270 with its origin at the body's middle,
  as motor-pid's.  Both are in `parts.JLC_ROTATION` and laid back onto our pads at 0.00 mm.
- **The relay's click at full volume** (OUT can reach a rail at the hand-over): written into the
  handbook's caution and the design notes; a two-diode limiter at the knob's wiper is a rev B idea.
- **motor-pid**: the MSK12C02 model scale confirmed (the VRML is drawn in mm, the footprint had
  scale 1 where every other model has 1/2.54) and fixed there (its Response 16, with a before and
  after render).  Only the footprint, the board's five model scales and two renders changed; its
  gerbers and plots, which this container's KiCad 10.0.8 and libraries regenerate with other
  headers, were left as they were.
- **Build:** ERC 0, 388 circuit checks, the simulation within tolerance, DRC 0 at every severity
  with schematic parity, all fab checks, 19 of 19 document claims; a second `./make.py` changes
  no file.

### What would most likely make this block dead on arrival

| risk | how likely | what shows it, what rescues it |
|---|---|---|
| the sleeve not on J9's lone pin | low: the maker's table, KiCad and JLCPCB agree | before plugging in, J9's sleeve to GND reads 0 ohm |
| loud in the ears at a switch-off | moderate: the arithmetic says OUT can reach a rail for a moment | VOLUME low until the level is known; the limiter of rev B by hand |
| the jack's stock (353) | low for one board | SJ1-3524-SMT-TR, the surface-mount twin, on a new footprint |
| JLCPCB fits the jack or the knob turned | very low: both are keyed by their holes and fit JLCPCB's drawing at 0.00 mm | `PLACEMENT_CHECKS.txt` |
