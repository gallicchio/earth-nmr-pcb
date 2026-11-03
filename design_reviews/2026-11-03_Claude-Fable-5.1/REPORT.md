# Design review: Earth's Field NMR rev A, commit d4e3f9e (main, 2026-11-02)

*Reviewer: Claude (Fable 5.1), the board's author, reviewing first, with no other
report read.  2026-11-03, 05:30-08:30 UTC.  Jason's brief: "a top to bottom design
review of this board, from the intention, architecture, schematic, and PCB.  Focus on
anything that could prevent it from working out of the box.  Actually look at every
schematic label and PCB silk screen to make sure it's clear and meets the standards of
CLAUDE_PCB.md."*

## Verdict

**Order after the named fixes.**  Nothing found would keep the board from seeing
protons: the physics, the sequencer's order in every case tried, the relay's pinout
(now read off Hongfa's own wiring diagram), the receiver's gains and the switch-off
all hold.  One circuit fault (1) can make the external-trigger input misbehave with
a bipolar generator; the rest are things a reader would stumble on: text drawn over
wires and symbols on the sheet, connector limits missing from the silkscreen, and
two numbers in the documents that are not what the board does.  Every fix is a few
lines in the generators; all were applied, rebuilt and re-checked in the same
session (the commit after this one).

## Findings

| # | severity | where | what | evidence | fix |
|---|---|---|---|---|---|
| 1 | **major** | POLARIZE IN: D12, U8 | A negative input drives U8's + input to -0.7 V (the BAV99's forward drop), below the TS391's absolute-maximum -0.3 V; the datasheet promises a correct output only above it.  A generator's bipolar square wave (the obvious drive) does this every half cycle | ST TS391 datasheet, abs. max. table "Input voltage -0.3 to 36 V" and note 3: "The low input voltage state must not be less than -0.3 V" | D12 becomes a BAT54S (Schottky pair, same SOT-23 pinout, C47546, basic), clamping at about -0.35 V, and R59 (10k) between the clamped node and the comparator's pin keeps the pin's own junction current to microamps.  Threshold and hysteresis unchanged |
| 2 | minor | sheet: D5/D6, LED3's note, D7's note, R43 | Text drawn across wires and symbols: "SMBJ33A" over D5's body, "LED3: the supply is there" crossed by the V POL column, D7's four-line note crossed by D9's column, R43's "100k" on J7's ground symbol | the 250 dpi crops of the sheet (`sch_polsup.png`, `sch_tank_l.png`, `sch_polin.png` in this directory); `check_schematic.py` tests text against text only | the parts and notes moved; the checker now also tests every text box against every wire segment |
| 3 | minor | sheet: J4, J7, U10, U12, R49/R50, R9, LED1/LED2 | Labels colliding with symbol graphics: the mirrored jacks' "J4"/"J7" on the shield pin's number; "U10"/"U12" running into the output pin's "1" ("U121"); the DELAY and HOLD loop names against "220k"/"270k"; "+15V" against "K1 coil 1028 ohm"; the two lamps' ground symbols drawn on top of each other (a bow-tie) | `sch_j4.png`, `sch_out_phones.png`, `sch_switches.png`, `sch_relay_sync.png`, `sch_power.png` | offsets changed; the 3-character references start nearer the triangle; the lamps' grounds 10 mm apart |
| 4 | minor | sheet: title block | Comment 1 runs out of the title block ("...(46.0 uT, IGRF-14, 2026-11-01): 9" and the frame) | `sch_bottom.png` | split into two comments |
| 5 | minor | board: J7, J4, J3 | Connectors without their limits (CLAUDE_PCB §6: "every connector that leaves the board is labelled with what it is for and its limits"): POLARIZE IN has no "±30 V max", CAL IN no "5 Vpp max", and the coil's 130 V warning is on the back only | `front_10.png`, `front_00.png` | the three lines added where the connectors are |
| 6 | minor | board: RV1, RV2, J1, J9 | RV1 and RV2 do not say which way is longer (RV3 says "clockwise louder"); J1's screws carry no name each (only the box's "J1: +15 V, ground, -15 V"); the headphone jack has only "J9" beside it, its name being the box's title 50 mm away | `front_12.png`, `front_02.png` | "clockwise longer" at each trimmer, "+15" / "-15" at J1's outer screws, "PHONES" at the jack |
| 7 | nit | sheet and board | "+/-30 V max": KiCad's font has ± (CLAUDE_PCB §6) | `sch_polin.png` | "±30 V max" |
| 8 | nit | sheet: SYNC OUT | "0 / 14 V through 1k": Q3 is a follower off a 10k base resistor; open it gives about 13 V, and 0.6 V into a 50 ohm scope | arithmetic: Ve = 13.6 - 0.7 - Ib x 10k | "0 / 13 V into a high impedance" |
| 9 | nit | handbook, design notes | "1 V into CAL IN gives about 4 V at OUT on LOW": the 4 V is the simulation's, for a 50 ohm generator SET to 1 V, which is 0.5 V at the jack's 51 ohm load.  A generator that displays its level into 50 ohm, set to 1 V, gives 8 V | `sim/nmr_sim.py` `Vcal ... AC 1` behind `Rgen 50` into R13 | say "0.5 V at the jack" in both documents |
| 10 | minor | handbook, sheet | "6-30 V, up to 3 A": the reference coil (8.9 ohm) draws 3.4 A from 30 V, past F1's 3 A hold and the relay contacts' 3 A rating | 30 / 8.86 | the supply limit for the reference coil is 26 V (3 A x 8.86 ohm); said on the sheet, the board's back and in the handbook, computed in design.py |
| 11 | info | SW1 | The silkscreen's ON side (toward pads 1-8) rests on the footprint's reading of KingTek's drawing, which prints ON on the body on one long side and the numbers 1-8 on the other; which pin row is 1-8 is not written.  KiCad's own KingTek DSHP08 footprint puts "on" at its pin-1 row, so the reading agrees with the library's | KingTek DSIC08 drawing; `Button_Switch_SMD:SW_DIP_SPSTx08_Slide_KingTek_DSHP08TS` | none; already in PLACEMENT_CHECKS (JLCPCB's preview draws the body with its marking) and in the DOA list: a wrong side costs nothing but reading the switches inverted |

## 1. The intention and the physics

- **What it must do** (README, DESIGN_NOTES): polarize a litre of water at 7.8 mT
  (1.5 A, 916 turns, 5.2 mT/A), switch the field off faster than the protons can
  follow, and listen at 1960 Hz with a tank and a x20301 chain.  Re-derived: B_p =
  µ0 N I / sqrt(l² + (2r)²) = 7.8 mT; the magnetization M = χ B_p with χ = µ0 n γ²ħ²/(4 k T)
  gives, by reciprocity, 1.2 µV in the coil; Q = ωL/R = 37 makes it 45 µV across the
  tank; x20301 and the chain's -0.9 dB at f_L give 0.8 V at OUT.  The simulation from the
  netlist agrees (0.83 V).
- **Non-adiabatic switch-off.**  The clamp holds the drain at 127 V, so dI/dt = (127 -
  13) V / 26.8 mH = 4.3 kA/s.  The Earth's field (46 µT) is the coil's field at 9 mA,
  which the ramp crosses in 2 µs; the field's direction swings through a radian in
  about that time, against 80 µs for a radian of Larmor precession.  Non-adiabatic by
  a factor of 40.  Holds.  (The simulation's 0.39 ms ramp is the whole 1.5 A; the part
  that matters is its last 9 mA.)
- **The hand-over.**  When the relay releases, both coil leads sit at V POL (13 V) with
  no current, and move onto a tank at 0 V.  The common mode goes through the INA's
  rejection and the 1 M bias resistors; the differential step comes from the two leads'
  unequal stray capacitance to ground (cable, coil), of order 1 mV on the 246 nF bank,
  which saturates the chain for ln(350) x 6 ms = 35 ms (the tank's ring-down time
  constant is 2Q/ω0 = 6 ms).  The handbook already says "a few tens of milliseconds of
  relay settling"; the FID lasts a second or more in a clean field.  Acceptable, noted.
- **The relay switches no current**: closes 18 ms before Q1 turns on (operate time
  4 ms), opens 15 ms after Q1 turns off (the ramp is 0.4 ms at 1.5 A, 0.7 ms at 3 A,
  and "1/2 L I² < 1 J" on the sheet bounds any coil to 7 ms).  Holds.
- **Energies.**  30 mJ per shot into the SMCJ100A at 1.5 A, 120 mJ at 3 A, against a
  1.5 kW / 10-1000 µs part (about 1.5 J); 30 mW average at one shot per few seconds.

## 2. The architecture

- **One coil, a DPDT relay, dry switching**: right for a signal relay; the contact
  rating (3 A, AgNi + Au, bifurcated) covers both jobs.  The gold flash survives
  because nothing is ever made or broken under load.
- **The sequencer in four parts, no logic**: POL CMD -> U10 (RELAY at once, held 15 ms
  by R50/C56 through D14) and U9 (GATE 18 ms later by R49/C55, dropped at once by D13).
  Walked through: power-up (both capacitors empty, both outputs low, the 555 starts high
  -> RELAY, then GATE 18 ms later); MODE to LISTEN mid-polarize (GATE off at once, the
  ramp, RELAY 15 ms later); POLARIZE IN pulsed faster than the delays (a 10 ms pulse
  pulls the relay and never the gate; a 100 Hz square wave holds the relay in and never
  charges C55 past 7.3 V).  Safe in each.
- **TS391 common mode**: the delay nodes charge to 13.3 V, past the TS391's VCC - 1.5 V
  common-mode limit (13.2 V), with the other input at 7.3 V.  The datasheet's note 3:
  with one input in range the output is correct.  Holds.
- **Supplies**: ±14.67 V after the SS34s; OPA197 (36 V max, RRIO), TS391 (36 V), NE555
  (16 V), all inside.  About 45 mA on +15 V (eight OPA197, three TS391, the 555, the
  relay coil 14 mA, the lamps), 15 mA on -15 V, plus the headphone drive's 30 mA peaks.
  "100 mA a rail" holds.
- **Ratings at the worst input**: R44 (10k) at -30 V in: 88 mW in a 125 mW 0805, warm
  but inside; F1 36 V, C5 50 V, D6 33 V standoff against a 30 V supply; R4 0.9 W of 2 W
  at 3 A; Q1 0.23 W.  Finding 10: the reference coil at 30 V is 3.4 A, over F1's hold
  and the relay's 3 A.

## 3. Pinouts

- **K1, HFD3/12** (the first-round DOA list's likeliest fault): Hongfa's "Wiring
  Diagram (Bottom view), Single side stable, No energized condition" (datasheet p. 33,
  read at 500 dpi this session): coil 1 (+) and 12 (-); pole A's common 4 rests on 3
  and moves to 5; pole B's common 9 rests on 10 and moves to 8.  That is the symbol
  (`earthnmr:HFD3_Split`) and the circuit (3-10 the tank, 5 V POL, 8 the drain, 1 on
  +15 V, 12 to Q2).  The datasheet's "Notice" calls the relay polarized ("if correct
  polarity is not applied to the coil terminals, the relay does not operate
  properly"), so the coil's sense matters and is right.  JLCPCB's land pattern lies on
  ours by pin number at 0.00 mm.  What remains is that the footprint's pin numbers are
  KiCad's reading of the G6S-2 pattern, which the fit confirms.  Retired to low.
- **TS391**: 1 OUT, 2 V-, 3 IN-, 4 IN+, 5 V+ (ILT; the RILT differs).  JLCPCB's symbol
  agrees pin for pin (`check_pinouts.py`).
- **BAV99 / BAT54S**: 1 = A1, 2 = K2, 3 = K1/A2, the same for both parts (Nexperia):
  pin 3 on the input, 1 to ground, 2 to +15 V.  Right way round on the sheet (checked
  by the diode arrows in `sch_polin.png`).
- **D10/D11, D13/D14**: the 555's charge path +15 -> R40 -> RV1 -> D10 (anode on
  DIS, cathode on C) -> C, the discharge C -> D11 -> R41 -> RV2 -> DIS; D13's cathode
  on POL CMD, D14's anode on POL CMD.  All as the arithmetic assumes.
- **SW2/SW3/SW4 sense**: the MSK12C02's knob slides toward the pin it connects; LOW/HIGH,
  EXT/TIMER, LISTEN/RUN are printed at the ends the pins are on.  Right.
- **SW1**: finding 11.
- **Q1, Q2, Q3, the SOT-23-5s, the SMA/SMB/SMC diodes, the jack**: unchanged since the
  first-round checks; the jack's three sources agree (Response 2).

## 4. The schematic, label by label

Every block of the A1 sheet was cropped at 250 dpi and read (`sch_*.png` here).
Findings 2, 3, 4, 7, 8.  Everything else: the flow is left to right and power from
the top; every stage has its title and a note at the node with its numbers; every
switch position is written beside the switch; the bypass capacitors are at their
pins; the ground symbols point down except where ground really is above (R11, R22,
the -15 V bypasses).  The checker (`check_schematic.py`) passed the sheet with six
text-on-wire or text-on-symbol collisions in it, because it tests only text against
text and the frame: it now tests text against wires too.

## 5. The board, label by label

The front and back were rendered from KiCad's own SVG export at 400 dpi and read in
six tiles each (`front_*.png`, `back_*.png`).  Findings 5 and 6.  Everything else:
every part is named and valued where it is; every stage is in a dashed box with its
name and numbers; the switches say what each position does at the position; the
relay's pins are numbered and its legend says which contacts make when; the DIP's
columns carry their capacitance; the 26 loops are named at the loop; the coil loop and
the three hops read as drawn; the identity (name, authors, URL, date, rev A, QR) is
there; the layer markers 1-4 are in copper at one spot; the back carries the user's
instructions.  DRC 0 at every severity with parity (the build).

## 6. The documents

Findings 9 and 10.  The 19 checked claims match the build; the numbers quoted in the
README, handbook and design notes were read against `sim/design.json` and
`sim/results.json` by hand as well.

## 7. What could not be checked

- The coil's real self-capacitance and the hand-over transient's size: simulation
  only (200 pF assumed in the switch-off deck).
- The TS391's behaviour with an input between -0.3 V and -0.35 V (the Schottky's drop):
  the datasheet draws the line at -0.3 V; R59 makes whatever happens there carry
  microamps.
- JLCPCB's preview (the rotation table's three "predicted" entries that no preview
  has shown: the jack, the knob, the relay's datum): `PLACEMENT_CHECKS.txt`.

## 8. What the first board would most likely die of, now

1. The hand-over transient longer than estimated (a coil with much more stray
   capacitance): the first 50-100 ms after SYNC OUT falls are junk; the FID is still
   there after.  Watch OUT on LOW first.
2. SW1's ON side printed the wrong way round: read the body's own mark.
3. The polarizing current's return through the plane upsetting the receiver: it
   flows only while the receiver is disconnected.
4. Thin stock: the BNC (215) and the headphone jack (353).

## Patches

Applied in the commit that follows this report (see `CLAUDE_CODE_CHAT.md`, Response
3): `scripts/gen_sch.py`, `scripts/check_schematic.py`, `scripts/parts.py`,
`sim/design.py`, `scripts/check_circuit.py`, `scripts/layout.py`,
`scripts/gen_outputs.py`, the three documents.
