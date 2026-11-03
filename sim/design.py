#!/usr/bin/env python3
"""The design arithmetic, in one place: every value the circuit computes.

    python3 sim/design.py          writes sim/design.json and prints the budget

The schematic generator reads sim/design.json (each computed passive by the
key of the parts table it was fitted to), the circuit check asserts the
netlist against it, and the documents quote it.  Change a target here and
`./make.py` carries it through the sheet, the board, the simulation and the
handbook.

Everything is evaluated twice: as computed, and as FITTED with the stocked
values the schematic draws (CLAUDE_PCB.md, "Evaluate the design as fitted").
"""
import cmath, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import parts                                    # noqa: E402

OUT = os.path.join(HERE, "design.json")

# ------------------------------------------------------------ the physics --
GAMMA_HZ_PER_T = 42.577478e6        # proton gyromagnetic ratio / 2 pi (CODATA 2018, in water: 42.5764)
MU0 = 4e-7 * math.pi
K_B = 1.380649e-23
HBAR = 1.054571817e-34
GAMMA = 2 * math.pi * GAMMA_HZ_PER_T
N_PROTONS_WATER = 6.69e28           # 1H per m^3 in water at 20 C (2 x 3.343e28 molecules)
T_SAMPLE = 293.0

# The field where the board will be used first: Harvey Mudd College, Claremont CA,
# IGRF-14 for 2026-11-01 at 350 m (ppigrf 2.1): F = 46028 nT, inclination
# 58.9 deg down, declination 11.2 deg E.  Buildings, steel and cars move it by
# hundreds of nT; the bench measures it.
SITE = dict(name="Harvey Mudd College, Claremont CA", F_nT=46028.0, incl_deg=58.89,
            decl_deg=11.23, source="IGRF-14, 2026-11-01")
# The field anywhere on Earth: 22 uT (the South Atlantic anomaly) to 67 uT (near the poles).
F_WORLD_nT = (22000.0, 67000.0)


def larmor(F_nT):
    return GAMMA_HZ_PER_T * F_nT * 1e-9


F_L = larmor(SITE["F_nT"])

# ----------------------------------------------------------- the coil -------
# The coil the handbook recommends winding: 4 layers of AWG 20 enamelled copper
# over 200 mm of a 3-inch PVC pipe (88.9 mm outside), round a 1 L bottle of water.
AWG20 = dict(d_bare=0.812e-3, d_ins=0.87e-3, ohm_per_m=33.31e-3)
COIL = dict(former_od=88.9e-3, length=0.200, layers=4, wire="AWG 20 (0.81 mm) enamelled",
            sample_litres=1.0, sample_d=0.085)


def coil_numbers(c=COIL, w=AWG20):
    per_layer = int(c["length"] / w["d_ins"])
    N = per_layer * c["layers"]
    depth = c["layers"] * w["d_ins"]
    r_mean = (c["former_od"] + depth) / 2
    wire_m = N * 2 * math.pi * r_mean
    R = wire_m * w["ohm_per_m"]
    # Wheeler's multilayer formula: L(uH) = 31.6 N^2 r^2 / (6 r + 9 l + 10 c), metres
    L = 31.6 * N ** 2 * r_mean ** 2 / (6 * r_mean + 9 * c["length"] + 10 * depth) * 1e-6
    # the field at the centre per ampere (a finite solenoid) and its mean over the sample
    B_per_A = MU0 * N / math.sqrt(c["length"] ** 2 + (2 * r_mean) ** 2)
    return dict(N=N, per_layer=per_layer, r_mean=r_mean, wire_m=wire_m, R=R, L=L,
                B_per_A=B_per_A, B_per_A_mean=0.85 * B_per_A)


# -------------------------------------------------------- stocked values -----
def ohms(text):
    t = text.replace("R", "")
    mult = 1.0
    if t.endswith("k"):
        mult, t = 1e3, t[:-1]
    elif t.endswith("M"):
        mult, t = 1e6, t[:-1]
    return float(t) * mult


def farads(text):
    t = text.replace("_C0G", "").replace("F", "")
    for suf, m in (("u", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if t.endswith(suf):
            return float(t[:-1]) * m
    return float(t)


R_STOCK = {k: ohms(k) for k in parts.PASSIVES if k[-1] in "kRM" and not k.endswith("nF")}
C0G_STOCK = {k: farads(k) for k in ("3.3nF", "6.8nF", "10nF", "47nF", "100nF_C0G")}


def nearest_r(target):
    return min(R_STOCK, key=lambda k: abs(math.log(R_STOCK[k] / target)))


# ------------------------------------------------------------- the tank ------
# A binary bank of C0G capacitance, 3.3 nF steps: each DIP switch adds one
# weight, built from the five stocked C0G values (CLAUDE_PCB.md section 12:
# class 1 ceramic for anything that sets a frequency).
BANK = [                    # (switch, [parts in parallel])
    (1, ["3.3nF"]),
    (2, ["6.8nF"]),
    (3, ["10nF", "3.3nF"]),
    (4, ["10nF", "10nF", "6.8nF"]),
    (5, ["47nF", "6.8nF"]),
    (6, ["100nF_C0G", "6.8nF"]),
    (7, ["100nF_C0G", "100nF_C0G", "10nF"]),
    (8, ["100nF_C0G", "100nF_C0G", "100nF_C0G", "100nF_C0G", "10nF", "10nF"]),
]
C_TVS = 390e-12            # the SMBJ12CA across the tank (datasheet, 0 V)


def bank_weights():
    return [sum(C0G_STOCK[k] for k in ks) for (_, ks) in BANK]


def bank_settings(C_target, C_fixed=C_TVS):
    """The DIP setting (switches 1-8 on/off) nearest C_target."""
    w = bank_weights()
    best = None
    for code in range(256):
        C = C_fixed + sum(w[i] for i in range(8) if code >> i & 1)
        if best is None or abs(C - C_target) < abs(best[1] - C_target):
            best = (code, C)
    return best


# ------------------------------------------------------- the preamplifier ----
INA = dict(R_series="1k", R_bias="1M", R_f="10k", R_g="200R", R_diff="10k")
OPA197_EN = 5.5e-9          # V/rtHz at 1 kHz (datasheet table)
OPA197_IN = 1.5e-15         # A/rtHz (datasheet, f = 1 kHz)

# ------------------------------------------------------------ the filters ----
F_HP = 700.0                 # 4th-order Butterworth high-pass: kills 60 Hz and its first harmonics
F_LP = 4000.0                # 2nd-order Butterworth low-pass: the top of the band, and anti-alias
Q_BW4 = (0.5412, 1.3066)     # the two sections of a 4th-order Butterworth
Q_BW2 = 0.7071
C_HP = "10nF"                # both capacitors of each high-pass section
LP_C = ("6.8nF", "3.3nF")    # the low-pass's feedback and shunt capacitors (Q = 0.5 sqrt(C1/C2))


def hp_section(R1, R2, C):
    """Unity-gain Sallen-Key high-pass: input - C - A - C - B (+IN), R1 from A
    to the output, R2 from B to ground."""
    w0 = 1 / (C * math.sqrt(R1 * R2))
    return w0 / (2 * math.pi), 0.5 * math.sqrt(R2 / R1)


def fit_hp(Q):
    C = C0G_STOCK[C_HP]
    best = None
    for k1, r1 in R_STOCK.items():
        for k2, r2 in R_STOCK.items():
            f0, q = hp_section(r1, r2, C)
            err = (math.log(f0 / F_HP)) ** 2 + (2 * math.log(q / Q)) ** 2
            if best is None or err < best[0]:
                best = (err, k1, k2, f0, q)
    return dict(R1=best[1], R2=best[2], C=C_HP, f0=best[3], Q=best[4])


def lp_section(R1, R2, C1, C2):
    """Unity-gain Sallen-Key low-pass: input - R1 - A - R2 - B (+IN), C1 from A
    to the output, C2 from B to ground."""
    w0 = 1 / math.sqrt(R1 * R2 * C1 * C2)
    return w0 / (2 * math.pi), math.sqrt(R1 * R2 * C1 * C2) / (C2 * (R1 + R2))


def fit_lp():
    C1, C2 = (C0G_STOCK[k] for k in LP_C)
    best = None
    for k, r in R_STOCK.items():
        f0, q = lp_section(r, r, C1, C2)
        err = (math.log(f0 / F_LP)) ** 2
        if best is None or err < best[0]:
            best = (err, k, f0, q)
    return dict(R1=best[1], R2=best[1], C1=LP_C[0], C2=LP_C[1], f0=best[2], Q=best[3])


def h_hp(f, f0, Q):
    s = 1j * f / f0
    return s * s / (s * s + s / Q + 1)


def h_lp(f, f0, Q):
    s = 1j * f / f0
    return 1 / (s * s + s / Q + 1)


# ------------------------------------------------------------- the gain ------
GAIN = dict(R_f="200k", R_lo="10k", R_hi="1k")      # the last stage: 1 + Rf/Rg
OUT_R = "1k"                                          # in series with OUT and SYNC OUT
# HEADPHONES: OUT through R_feed onto the VOLUME knob, a follower (U12), and R_out to
# each earpiece of a stereo set (the signal is mono: tip and ring alike).  R_feed sets
# the loudest the knob can go; R_out keeps a mono plug (its sleeve shorting the ring)
# and a saturated OUT inside the follower's current and an 0805's power.
PHONES = dict(R_feed="62k", RV="10k", R_out="100R")
Z_PHONE = 32.0                                        # ohm, a typical earpiece
SENS_DB_MW = 100.0                                    # dB SPL per mW, a typical earpiece
V_OUT_MAX = 14.8                                      # OUT saturated: the OPA197 swings to its rails
R_0805_W = 0.125

# ------------------------------------------------------- the sequencer -------
VCC = 15.0 - 0.33          # the bench's 15 V less the SS34 at about 50 mA
V_DIODE = 0.5              # 1N4148W at a few microamps to a milliamp
V_OH_555 = VCC - 1.4       # NE555 output high, lightly loaded (datasheet: VCC - 1.7 V at 100 mA)
TIMER = dict(C="1uF", n_C=3, R_min="100k", RV="2M")
DELAY = dict(R_gate="220k", R_hold="270k", C="100nF_C0G", R_th_top="10k", R_th_bot="10k")
EXT = dict(R_series="10k", R_pd="100k", R_top="100k", R_bot="10k", R_hyst="1M", R_pu="10k", R_in="10k")
V_EXT_MAX = 30.0           # what POLARIZE IN is promised to survive, either polarity
RELAY = dict(coil_ohm=1028.0, operate_ms=4.0, release_ms=4.0, pull_in_V=9.0, max_V=24.0)
GATE = dict(R_pu="4.7k", R_g="47R", R_gs="100k")
TVS_VBR = (111.0, 123.0)   # SMCJ100A breakdown, min and max
TVS_VC_9A = 162.0          # at 9.3 A
POL_SUPPLY = (6.0, 30.0)   # the polarizing supply the board accepts
I_POL_MAX = 3.0            # the relay's 3 A at 30 VDC; the fuse holds 3 A


def tvs_clamp(i):
    """The SMCJ100A's voltage at current i: its typical breakdown plus its slope
    resistance up to the 9.3 A point."""
    vbr = sum(TVS_VBR) / 2
    return vbr + (TVS_VC_9A - TVS_VBR[1]) / 9.3 * i


def timer_k():
    """Charge and discharge constants of the diode-steered 555: t = k R C."""
    hi = VCC - V_DIODE
    lo = V_DIODE + 0.1
    kc = math.log((hi - VCC / 3) / (hi - 2 * VCC / 3))
    kd = math.log((2 * VCC / 3 - lo) / (VCC / 3 - lo))
    return kc, kd


def main():
    d = {}
    # the field and the frequency
    d["site"] = dict(SITE, f_L=F_L)
    d["world"] = dict(F_nT=F_WORLD_nT, f_L=[larmor(f) for f in F_WORLD_nT])
    # the coil and the sample
    c = coil_numbers()
    w_L = 2 * math.pi * F_L
    Q = w_L * c["L"] / c["R"]
    C_res = 1 / (w_L ** 2 * c["L"])
    Rp = Q * Q * c["R"]
    m_per_T = N_PROTONS_WATER * GAMMA ** 2 * HBAR ** 2 * 0.75 / (3 * K_B * T_SAMPLE)   # A/m per tesla
    I_pol = 1.5
    B_p = c["B_per_A"] * I_pol
    V_s = COIL["sample_litres"] * 1e-3
    emf = w_L * m_per_T * I_pol * c["B_per_A_mean"] ** 2 * V_s       # reciprocity, M = chi B_p
    code, C_set = bank_settings(C_res)
    d["coil"] = dict(COIL, N=c["N"], R=c["R"], L=c["L"], wire_m=c["wire_m"], Q=Q, C_res=C_res, Rp=Rp,
                     B_per_A=c["B_per_A"], I_pol=I_pol, B_p=B_p, V_pol=I_pol * c["R"],
                     P_pol=I_pol ** 2 * c["R"], energy=0.5 * c["L"] * I_pol ** 2,
                     chi=MU0 * m_per_T, M0=m_per_T * B_p, emf=emf, v_tank=emf * Q,
                     dip_code=code, dip_C=C_set, dip_f=1 / (2 * math.pi * math.sqrt(c["L"] * C_set)))
    # the noise at the preamplifier's input, per root hertz
    en_tank = math.sqrt(4 * K_B * T_SAMPLE * Rp)
    en_amp = OPA197_EN * math.sqrt(2)
    en_series = math.sqrt(2 * 4 * K_B * T_SAMPLE * ohms(INA["R_series"]))
    en_rg = math.sqrt(4 * K_B * T_SAMPLE * ohms(INA["R_g"]))
    in_bias = math.sqrt(4 * K_B * T_SAMPLE / ohms(INA["R_bias"]))
    en_bias = in_bias * Rp / math.sqrt(2)
    en_total = math.sqrt(en_tank ** 2 + en_amp ** 2 + en_series ** 2 + en_rg ** 2 + en_bias ** 2)
    nbw = math.pi / 2 * F_L / Q
    d["noise"] = dict(tank=en_tank, amp=en_amp, series=en_series, rg=en_rg, bias=en_bias, total=en_total,
                      nf_db=20 * math.log10(en_total / en_tank), nbw=nbw,
                      v_noise=en_total * math.sqrt(nbw),
                      snr_db=20 * math.log10(d["coil"]["v_tank"] / (math.sqrt(2) * en_total * math.sqrt(nbw))))
    # the bank
    wts = bank_weights()
    d["bank"] = dict(switches=[dict(sw=s, parts=ks, C=wts[i]) for i, (s, ks) in enumerate(BANK)],
                     C_min=C_TVS, C_max=C_TVS + sum(wts), step=wts[0])
    gaps = []
    for i in range(1, 8):
        gaps.append(wts[i] - sum(wts[:i]) - wts[0])
    d["bank"]["worst_gap"] = max(gaps)
    # tuning range: the coil inductance the bank resonates at the site and over the world
    d["bank"]["L_range_site"] = [1 / (w_L ** 2 * (C_TVS + sum(wts))), 1 / (w_L ** 2 * (C_TVS + wts[0]))]
    # the preamplifier
    g_ina = 1 + 2 * ohms(INA["R_f"]) / ohms(INA["R_g"])
    d["ina"] = dict(INA, gain=g_ina)
    # the filters, fitted
    hp1, hp2, lp = fit_hp(Q_BW4[0]), fit_hp(Q_BW4[1]), fit_lp()
    d["hp1"], d["hp2"], d["lp"] = hp1, hp2, lp
    g_lo = 1 + ohms(GAIN["R_f"]) / ohms(GAIN["R_lo"])
    g_hi = 1 + ohms(GAIN["R_f"]) / ohms(GAIN["R_hi"])
    d["gain"] = dict(GAIN, lo=g_lo, hi=g_hi, total_lo=g_ina * g_lo, total_hi=g_ina * g_hi,
                     db_lo=20 * math.log10(g_ina * g_lo), db_hi=20 * math.log10(g_ina * g_hi))

    def chain(f):
        return abs(h_hp(f, hp1["f0"], hp1["Q"]) * h_hp(f, hp2["f0"], hp2["Q"]) * h_lp(f, lp["f0"], lp["Q"]))

    resp = {}
    for f in (60, 120, 180, 300, 420, 600, 700, 1000, F_WORLD_nT and larmor(F_WORLD_nT[0]), 1500, F_L,
              2500, larmor(F_WORLD_nT[1]), 4000, 8000, 20000):
        resp[f"{f:.0f}"] = 20 * math.log10(chain(f))
    d["filter_db"] = resp
    # corners of the whole chain (-3 dB)
    fs = [10 ** (k / 400) for k in range(800, 1800)]
    peak = max(chain(f) for f in fs)
    band = [f for f in fs if chain(f) >= peak / math.sqrt(2)]
    d["filter_band"] = dict(f_lo=band[0], f_hi=band[-1], peak_db=20 * math.log10(peak))
    d["out"] = dict(R=OUT_R)
    # the FID at the output, at HIGH gain, with the recommended coil
    d["fid_out_hi"] = d["coil"]["v_tank"] * d["gain"]["total_hi"] * chain(F_L)
    # the headphones: the knob fully clockwise
    k_max = ohms(PHONES["RV"]) / (ohms(PHONES["R_feed"]) + ohms(PHONES["RV"]))
    k_ear = Z_PHONE / (Z_PHONE + ohms(PHONES["R_out"]))

    def spl(v_peak):
        return SENS_DB_MW + 10 * math.log10((v_peak / math.sqrt(2)) ** 2 / Z_PHONE / 1e-3)

    fid_ear_hi = d["fid_out_hi"] * k_max * k_ear
    fid_ear_lo = fid_ear_hi * d["gain"]["lo"] / d["gain"]["hi"]
    i_short = V_OUT_MAX * k_max / ohms(PHONES["R_out"])
    d["phones"] = dict(PHONES, Z=Z_PHONE, sens_db_mw=SENS_DB_MW, k_max=k_max, k_ear=k_ear,
                       fid_ear_hi=fid_ear_hi, fid_ear_lo=fid_ear_lo, spl_hi=spl(fid_ear_hi), spl_lo=spl(fid_ear_lo),
                       spl_max=spl(V_OUT_MAX * k_max * k_ear),
                       i_short=i_short, p_short=i_short ** 2 * ohms(PHONES["R_out"]), p_rating=R_0805_W,
                       load_out=ohms(PHONES["R_feed"]) + ohms(PHONES["RV"]))
    assert d["phones"]["p_short"] < R_0805_W / 2, "R_out would run past half its rating into a short"
    assert 2 * i_short < 0.065, "both earpieces shorted would pull more than the OPA197 gives"
    # the sequencer
    kc, kd = timer_k()
    Ct = farads(TIMER["C"]) * TIMER["n_C"]
    rmin, rmax = ohms(TIMER["R_min"]), ohms(TIMER["R_min"]) + ohms(TIMER["RV"])
    d["timer"] = dict(TIMER, C_total=Ct, kc=kc, kd=kd, t_pol=[kc * rmin * Ct, kc * rmax * Ct],
                      t_listen=[kd * rmin * Ct, kd * rmax * Ct])
    v_th = VCC * ohms(DELAY["R_th_bot"]) / (ohms(DELAY["R_th_top"]) + ohms(DELAY["R_th_bot"]))
    Cd = farads(DELAY["C"])
    tau_g, tau_h = ohms(DELAY["R_gate"]) * Cd, ohms(DELAY["R_hold"]) * Cd
    t_gate = tau_g * math.log(V_OH_555 / (V_OH_555 - v_th))
    t_hold = tau_h * math.log((V_OH_555 - V_DIODE) / v_th)
    d["delay"] = dict(DELAY, v_th=v_th, tau_gate=tau_g, tau_hold=tau_h, t_gate=t_gate, t_hold=t_hold,
                      t_listen_start=t_hold + RELAY["release_ms"] * 1e-3,
                      margin_on=t_gate - RELAY["operate_ms"] * 1e-3)
    # the polarizing switch-off: the TVS holds the drain at its clamp voltage, the coil
    # sees that less the supply, and its current falls in a straight line
    v_c = tvs_clamp(I_POL_MAX)
    d["switch_off"] = dict(v_clamp_3A=v_c, v_clamp_max=TVS_VC_9A, v_ds_rating=200.0,
                           t_ramp_ref=c["L"] * I_pol / (tvs_clamp(I_pol) - 24.0),
                           LI_max=(t_hold) * (v_c - POL_SUPPLY[1]),
                           E_max_J=1.0)
    d["relay"] = dict(RELAY, V_coil=VCC - 0.1, I_coil=(VCC - 0.1) / RELAY["coil_ohm"])
    d["ext"] = dict(EXT, v_th=VCC * ohms(EXT["R_bot"]) / (ohms(EXT["R_top"]) + ohms(EXT["R_bot"])),
                    hyst=VCC * ohms(EXT["R_series"]) / ohms(EXT["R_hyst"]), v_max=V_EXT_MAX,
                    # the worst input: the clamp's current through R_series, and R_series's heat
                    i_clamp=V_EXT_MAX / ohms(EXT["R_series"]),
                    p_series=V_EXT_MAX ** 2 / ohms(EXT["R_series"]))
    assert d["ext"]["p_series"] < R_0805_W, "R44 would run past its rating at the input's limit"
    d["gate"] = dict(GATE)
    # the reference coil's resistance caps the supply that keeps it under the fuse's 3 A
    d["pol_supply"] = dict(V=POL_SUPPLY, I_max=I_POL_MAX, V_max_ref_coil=math.floor(I_POL_MAX * c["R"]))
    d["passives"] = sorted({INA["R_series"], INA["R_bias"], INA["R_f"], INA["R_g"], INA["R_diff"],
                            hp1["R1"], hp1["R2"], hp2["R1"], hp2["R2"], lp["R1"],
                            GAIN["R_f"], GAIN["R_lo"], GAIN["R_hi"], OUT_R, PHONES["R_feed"], PHONES["R_out"],
                            TIMER["R_min"], DELAY["R_gate"], DELAY["R_hold"], DELAY["R_th_top"],
                            *EXT.values(), GATE["R_pu"], GATE["R_g"], GATE["R_gs"]})
    json.dump(d, open(OUT, "w"), indent=1, sort_keys=True)
    report(d)
    return d


def report(d):
    c, n = d["coil"], d["noise"]
    print(f"  Larmor frequency at {d['site']['name']}: {d['site']['f_L']:.1f} Hz "
          f"({d['site']['F_nT']:.0f} nT); anywhere on Earth {d['world']['f_L'][0]:.0f}-{d['world']['f_L'][1]:.0f} Hz")
    print(f"  coil: {c['N']} turns, {c['L'] * 1e3:.1f} mH, {c['R']:.2f} ohm, Q {c['Q']:.0f}, "
          f"resonates with {c['C_res'] * 1e9:.0f} nF (DIP {c['dip_code']:08b}[::-1] -> {c['dip_C'] * 1e9:.1f} nF, "
          f"{c['dip_f']:.0f} Hz); {c['B_per_A'] * 1e3:.2f} mT/A")
    print(f"  at {c['I_pol']} A: {c['V_pol']:.1f} V, {c['P_pol']:.0f} W, B_p {c['B_p'] * 1e3:.1f} mT, "
          f"{c['energy'] * 1e3:.0f} mJ stored")
    print(f"  FID: {c['emf'] * 1e6:.2f} uV in the coil, {c['v_tank'] * 1e6:.0f} uV across the tank, "
          f"{d['fid_out_hi']:.2f} V at OUT on HIGH")
    print(f"  noise at the tank: {n['tank'] * 1e9:.1f} nV/rtHz from the coil, {n['total'] * 1e9:.1f} with the "
          f"preamplifier (NF {n['nf_db']:.1f} dB); single-shot SNR {n['snr_db']:.0f} dB in {n['nbw']:.0f} Hz")
    b = d["bank"]
    print(f"  bank: {b['C_min'] * 1e9:.1f}-{b['C_max'] * 1e9:.0f} nF in {b['step'] * 1e9:.1f} nF steps "
          f"(worst gap {b['worst_gap'] * 1e9:+.2f} nF); tunes {b['L_range_site'][0] * 1e3:.1f}-"
          f"{b['L_range_site'][1] * 1e3:.0f} mH at {d['site']['f_L']:.0f} Hz")
    for k in ("hp1", "hp2", "lp"):
        s = d[k]
        print(f"  {k}: {s['R1']} / {s['R2']}, f0 {s['f0']:.0f} Hz, Q {s['Q']:.3f}")
    fb = d["filter_band"]
    print(f"  band {fb['f_lo']:.0f}-{fb['f_hi']:.0f} Hz; 60 Hz {d['filter_db']['60']:.0f} dB, "
          f"180 Hz {d['filter_db']['180']:.0f} dB, 420 Hz {d['filter_db']['420']:.1f} dB")
    g = d["gain"]
    print(f"  gain: INA x{d['ina']['gain']:.0f}, LOW x{g['total_lo']:.0f} ({g['db_lo']:.1f} dB), "
          f"HIGH x{g['total_hi']:.0f} ({g['db_hi']:.1f} dB)")
    t = d["timer"]
    print(f"  timer: POLARIZE {t['t_pol'][0]:.2f}-{t['t_pol'][1]:.2f} s, LISTEN {t['t_listen'][0]:.2f}-"
          f"{t['t_listen'][1]:.2f} s")
    dl = d["delay"]
    print(f"  polarizing supply: {d['pol_supply']['V'][0]:.0f}-{d['pol_supply']['V'][1]:.0f} V, up to "
          f"{d['pol_supply']['I_max']:.0f} A; the reference coil draws that at {d['pol_supply']['V_max_ref_coil']:.0f} V")
    print(f"  gate on {dl['t_gate'] * 1e3:.1f} ms after the relay (margin {dl['margin_on'] * 1e3:.1f} ms); "
          f"relay held {dl['t_hold'] * 1e3:.1f} ms after the gate, listening from "
          f"{dl['t_listen_start'] * 1e3:.1f} ms")
    so = d["switch_off"]
    print(f"  switch-off: drain clamped at {so['v_clamp_3A']:.0f} V at 3 A ({so['v_ds_rating']:.0f} V part); "
          f"the reference coil ramps down in {so['t_ramp_ref'] * 1e3:.2f} ms; L x I up to "
          f"{so['LI_max']:.2f} H.A ramps inside the relay's hold")
    ph = d["phones"]
    print(f"  headphones: the knob full up, the FID {ph['fid_ear_hi'] * 1e3:.0f} mV at a {ph['Z']:.0f} ohm earpiece on "
          f"HIGH (~{ph['spl_hi']:.0f} dB SPL), {ph['fid_ear_lo'] * 1e3:.1f} mV on LOW, OUT at a rail ~{ph['spl_max']:.0f} dB; a shorted ring "
          f"{ph['i_short'] * 1e3:.0f} mA, {ph['p_short'] * 1e3:.0f} mW in R_out")


if __name__ == "__main__":
    main()
