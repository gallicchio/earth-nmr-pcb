#!/usr/bin/env python3
"""Query JLCPCB's parts library: stock, price breaks, Basic/Extended, MPN.

One endpoint does everything we need -- the same one the parts search on
jlcpcb.com uses:

    POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood
         /selectSmtComponentList        {"currentPage":1,"pageSize":N,
                                         "keyword":"C42879" or free text}

Every answer is cached on disk WITH THE TIME IT WAS FETCHED, because the whole
point of the annotated BOM is to say what stock was at a stated moment.  Re-run
with --refresh to re-query; otherwise a cache entry younger than MAX_AGE_H is
reused so that building the release ten times does not hammer their server.

Nothing here writes to the board or the schematic.  It is read-only.

    python3 tools/jlc_api.py C2286 "SN75161B"          search, Basic parts first
    python3 tools/jlc_api.py --refresh C2286           ignore the cache

(Copied from the ECP5-2ADC-2DAC project's tools/, where it was written.)
"""
import json, os, sys, time, urllib.request, urllib.error, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "jlc_cache.json")
URL = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood"
       "/selectSmtComponentList")
MAX_AGE_H = 24
UA = "Mozilla/5.0 (X11; Linux x86_64) kicad-release-tooling/1.0"


def _load():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(c):
    tmp = CACHE + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), indent=1, sort_keys=True)
    os.replace(tmp, CACHE)


_cache = _load()


def _post(keyword, page_size):
    body = json.dumps({"currentPage": 1, "pageSize": page_size,
                       "keyword": keyword}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": UA,
        "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if d.get("code") != 200:
                raise RuntimeError("API code %s for %r" % (d.get("code"), keyword))
            return d["data"]["componentPageInfo"].get("list") or []
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(2.0 * (attempt + 1))


def search(keyword, page_size=20, refresh=False):
    """Raw search.  Returns (list_of_parts, iso_timestamp_of_the_query)."""
    key = "s:%d:%s" % (page_size, keyword)
    ent = _cache.get(key)
    if ent and not refresh and ent.get("list") is not None:
        age = (time.time() - ent["fetched_epoch"]) / 3600.0
        if age < MAX_AGE_H:
            return ent["list"], ent["fetched"]
    lst = _post(keyword, page_size) or []
    now = datetime.datetime.now().astimezone()
    _cache[key] = {"list": lst, "fetched": now.isoformat(timespec="seconds"),
                   "fetched_epoch": time.time()}
    _save(_cache)
    time.sleep(0.35)                 # be polite to their server
    return lst, _cache[key]["fetched"]


def by_code(code, refresh=False):
    """Look one LCSC code up exactly.  Returns (part_dict_or_None, timestamp)."""
    lst, ts = search(code, page_size=5, refresh=refresh)
    for it in lst:
        if (it.get("componentCode") or "").upper() == code.upper():
            return it, ts
    return None, ts


# ---------------------------------------------------------------------------
def library_type(part):
    """'Basic', 'Preferred' or 'Extended' -- what JLCPCB charges you for.

    A Basic part carries no per-part setup fee.  An Extended one does (about
    $3 at the time of writing) and that fee is per DISTINCT part, not per
    placement, which is why the annotated BOM counts distinct extended parts.
    Preferred parts are Extended parts JLCPCB keeps on the machine anyway, so
    they behave like Basic for the setup fee.
    """
    t = (part.get("componentLibraryType") or "").lower()
    if t == "base":
        return "Preferred" if part.get("preferredComponentFlag") else "Basic"
    return "Preferred" if part.get("preferredComponentFlag") else "Extended"


def unit_price(part, qty):
    """Price per piece at `qty`, from the componentPrices break table."""
    best = None
    for br in part.get("componentPrices") or []:
        lo = br.get("startNumber") or 0
        hi = br.get("endNumber")
        hi = float("inf") if hi in (None, -1) else hi
        if lo <= qty <= hi:
            return float(br["productPrice"])
        if best is None or lo <= qty:
            best = float(br["productPrice"])
    if best is not None:
        return best
    ip = part.get("initialPrice")
    return float(ip) if ip is not None else 0.0


def order_qty(part, need):
    """How many JLCPCB will actually charge for.

    They add `lossNumber` attrition pieces per distinct part and enforce a
    minimum purchase, so the invoice quantity is not simply the placement
    count.  Getting this right is the difference between an estimate and a
    number you can check against the quote.
    """
    loss = int(part.get("lossNumber") or 0)
    minp = int(part.get("minPurchaseNum") or 1)
    return max(need + loss, minp, 1)


if __name__ == "__main__":
    ref = "--refresh" in sys.argv
    QTY = 20
    for kw in [a for a in sys.argv[1:] if not a.startswith("-")]:
        lst, ts = search(kw, page_size=40, refresh=ref)
        lst.sort(key=lambda it: (library_type(it) == "Extended", -(it.get("stockCount") or 0)))
        print("%s   (queried %s, %d hits)" % (kw, ts, len(lst)))
        for it in lst[:14]:
            q = order_qty(it, QTY)
            print("  %-11s %-9s %-26s %-12s stock %-8d $%.4f@%d | %s" % (
                it["componentCode"], library_type(it),
                (it.get("componentModelEn") or "")[:26],
                (it.get("componentSpecificationEn") or "")[:12],
                it.get("stockCount") or 0, unit_price(it, q), q,
                (it.get("describe") or "")[:80]))
