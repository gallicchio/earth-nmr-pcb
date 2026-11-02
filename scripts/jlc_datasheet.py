#!/usr/bin/env python3
"""Download the datasheet JLCPCB holds for an LCSC part code into ../datasheets/.

    python3 jlc_datasheet.py C187932 [C54408 ...]

LCSC's own datasheet URLs refuse scripted fetches; JLCPCB's file endpoint,
keyed by the dataManualFileAccessId the parts search returns, does not.
"""
import os, sys, re, urllib.request, jlc_api

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "datasheets")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

def fetch(code):
    part, ts = jlc_api.by_code(code)
    if part is None:
        print("%s: not found" % code); return None
    aid = part.get("dataManualFileAccessId")
    mpn = re.sub(r"[^A-Za-z0-9._-]+", "_", part.get("componentModelEn") or code)
    name = "%s_%s.pdf" % (mpn, code)
    path = os.path.join(OUT, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print("%s: already have %s" % (code, name)); return path
    urls = []
    if aid:
        urls.append("https://jlcpcb.com/api/file/downloadByFileSystemAccessId/%s" % aid)
    if part.get("dataManualUrl"):
        urls.append(part["dataManualUrl"])
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*",
                                                     "Referer": "https://jlcpcb.com/"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data[:4] != b"%PDF" and b"datasheet.lcsc.com/datasheet/pdf/" in data:
                # LCSC's datasheet URL now answers with an HTML viewer; the PDF
                # itself is linked from it (2026-11)
                m = re.search(rb"https://datasheet\.lcsc\.com/datasheet/pdf/[0-9a-f]+\.pdf", data)
                req = urllib.request.Request(m.group(0).decode(), headers={"User-Agent": UA, "Accept": "*/*",
                                                                          "Referer": "https://www.lcsc.com/"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
            if data[:4] == b"%PDF":
                os.makedirs(OUT, exist_ok=True)
                open(path, "wb").write(data)
                print("%s: %s (%d kB) from %s" % (code, name, len(data)//1024, u[:60]))
                return path
            print("%s: not a PDF from %s (%d bytes)" % (code, u[:60], len(data)))
        except Exception as e:
            print("%s: %s -> %s" % (code, u[:60], e))
    return None

if __name__ == "__main__":
    for c in sys.argv[1:]:
        fetch(c)
