#!/usr/bin/env python3
"""Fit a drawing to its paper: what is drawn on each page fills the page, less a margin, centred.

    python3 scripts/fit_pdf.py fit IN.pdf OUT.pdf [--paper letter] [--margin 12.7] [--caption TEXT]
    python3 scripts/fit_pdf.py check FILE.pdf ...

Copied from CostasLink-PYNQ-Z2's tools/fit_pdf.py (2026-10-29), with one change: Ghostscript is told to leave out
the document ID, the dates and the XMP packet (STABLE), so an unchanged board writes the same bytes and the
committed PDFs do not churn in git.

Jason, 2026-10-29: "The board in ./mfg/release/CostasLink-PYNQ-Z2_assembly_top.pdf should take up the entire
page (with a reasonable margin).  Right now, if I were to print it, I couldn't read it."  kicad-cli plots a
board 1:1 where it sits on its A4 sheet: the 120 x 100 mm board filled 41 % of the page's width, in the top
left corner.  Its --scale 0 (autoscale) is no cure: on the same A4 it filled 77 % of the height, 66 % of the
width, 10 pt off centre (KiCad 10.0.7, measured).

fit: each page's drawn box (Ghostscript's bbox device: every mark, the parts hanging over the board's edge
included) is scaled to fill the paper less the margin, centred, the paper turned to the drawing's shape.
Vector in, vector out: Ghostscript's pdfwrite with the transform as the page device's BeginPage.  --caption
goes in the bottom margin, "{scale}" in it replaced by the scale applied (a fitted drawing is no longer 1:1:
say so on the page).  Captions are ASCII (the standard Helvetica).

check: for each page, how much of the paper the drawing spans along its tighter axis and how far its centre
is from the page's; exit status 1 when a page fills less than FILL_MIN or sits off centre by more than
OFF_CENTRE_MAX.  It cannot see a drawing clipped at the page's edge (the bbox device stops there), nor a
schematic lost in a corner of its frame (the frame is drawn, and fills the page): look at those.

Needs Ghostscript (gs) and pdfinfo (poppler-utils) on the PATH.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

MM = 72 / 25.4                       # points per millimetre
PAPERS = {"letter": (612.0, 792.0),  # portrait, points: 8.5 x 11 in (US; what this lab's printers hold)
          "a4": (595.28, 841.89),    # 210 x 297 mm
          "tabloid": (792.0, 1224.0),  # 11 x 17 in
          "a3": (841.89, 1190.55)}   # 297 x 420 mm
MARGIN_MM = 12.7                     # half an inch: clear of every printer's unprintable edge (4-6 mm), room for a caption
CAPTION_PT = 8
STABLE = ["-dOmitID", "-dOmitInfoDate", "-dOmitXMP"]   # Ghostscript 9.55 and later
FILL_MIN = 0.80                      # a page fitted with half-inch margins spans 0.88 of Letter's 8.5 in
OFF_CENTRE_MAX = 0.03                # of the page's width or height


def bboxes(path):
    """Each page's drawn box (x0, y0, x1, y1), in points from the page's bottom-left corner."""
    r = subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=bbox", path],
                       capture_output=True, text=True, check=True)
    return [tuple(float(v) for v in m.groups())
            for m in re.finditer(r"%%HiResBoundingBox: (\S+) (\S+) (\S+) (\S+)", r.stderr)]


def page_sizes(path):
    """Each page's (width, height) in points."""
    r = subprocess.run(["pdfinfo", "-f", "1", "-l", "100000", path], capture_output=True, text=True, check=True)
    return [(float(w), float(h)) for w, h in re.findall(r"Page\s+\d+ size:\s+([\d.]+) x ([\d.]+)", r.stdout)]


def _ps_string(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def fit(src, dst, paper="letter", margin_mm=MARGIN_MM, caption=None):
    """Write dst: src with each page's drawing scaled and centred on `paper`.  Returns the scales applied."""
    pw, ph = PAPERS[paper]
    m = margin_mm * MM
    scales, parts = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for n, (x0, y0, x1, y1) in enumerate(bboxes(src), 1):
            bw, bh = x1 - x0, y1 - y0
            if bw <= 0 or bh <= 0:
                raise ValueError("%s: page %d is blank" % (src, n))
            W, H = (ph, pw) if bw > bh else (pw, ph)         # landscape for a wide drawing
            s = min((W - 2 * m) / bw, (H - 2 * m) / bh)
            tx, ty = (W - s * bw) / 2 - s * x0, (H - s * bh) / 2 - s * y0
            ps = "<< /BeginPage {pop %.4f %.4f translate %.6f dup scale}" % (tx, ty, s)
            if caption:
                text = _ps_string(caption.replace("{scale}", "%.2f" % s))
                # EndPage: (count reason -- bool); the caption on every showpage (reason 0), in device points
                ps += (" /EndPage {exch pop dup 0 eq {gsave initmatrix 0 setgray /Helvetica findfont %d scalefont"
                       " setfont %s dup stringwidth pop %.2f exch sub 2 div %.2f moveto show grestore} if 2 ne}"
                       % (CAPTION_PT, text, W, 0.6 * m - CAPTION_PT / 2))
            ps += " >> setpagedevice"
            part = os.path.join(tmp, "%04d.pdf" % n)
            subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", *STABLE, "-dFIXEDMEDIA",
                            "-dDEVICEWIDTHPOINTS=%.2f" % W, "-dDEVICEHEIGHTPOINTS=%.2f" % H,
                            "-dFirstPage=%d" % n, "-dLastPage=%d" % n, "-o", part, "-c", ps, "-f", src], check=True)
            scales.append(s)
            parts.append(part)
        out = os.path.join(tmp, "out.pdf")
        if len(parts) == 1:
            shutil.copyfile(parts[0], out)
        else:                                                # pages keep their own sizes
            subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", *STABLE, "-o", out] + parts,
                           check=True)
        shutil.copyfile(out, dst)                            # dst may be src
    return scales


def check(path, fill_min=FILL_MIN, off_max=OFF_CENTRE_MAX):
    """One line a page; True when every page fills its paper and sits in its middle."""
    ok = True
    for n, ((W, H), (x0, y0, x1, y1)) in enumerate(zip(page_sizes(path), bboxes(path)), 1):
        fill = max((x1 - x0) / W, (y1 - y0) / H)
        off = max(abs((x0 + x1) / 2 - W / 2) / W, abs((y0 + y1) / 2 - H / 2) / H)
        good = fill >= fill_min and off <= off_max
        ok &= good
        print("%s p%d: %.0f x %.0f mm page, drawing %.0f x %.0f mm, fills %.0f %%, off centre %.1f %%, margins "
              "L %.0f B %.0f R %.0f T %.0f mm  %s"
              % (os.path.basename(path), n, W / MM, H / MM, (x1 - x0) / MM, (y1 - y0) / MM, 100 * fill, 100 * off,
                 x0 / MM, y0 / MM, (W - x1) / MM, (H - y1) / MM, "ok" if good else "BAD"))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("src")
    f.add_argument("dst")
    f.add_argument("--paper", default="letter", choices=sorted(PAPERS))
    f.add_argument("--margin", type=float, default=MARGIN_MM, help="mm")
    f.add_argument("--caption")
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        scales = fit(a.src, a.dst, a.paper, a.margin, a.caption)
        print("%s: %d page(s), scale %s" % (a.dst, len(scales), ", ".join("%.3f" % s for s in scales)))
        return 0 if check(a.dst) else 1
    return 0 if all([check(p) for p in a.files]) else 1


if __name__ == "__main__":
    sys.exit(main())
