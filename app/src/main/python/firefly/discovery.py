"""Finding Stumps over Wi-Fi, and how good a link to each one is.

Where a phone can find a Stump (CLIENT_QUICKSTART.md, Addresses and Chained
Stumps):

  * here     the gateway of the Wi-Fi it joined: 192.168.4.1 on a lone Stump,
             192.168.<n>.1 along a chain.
  * nearby   other Stumps' hotspots, from a Wi-Fi scan (done by the app);
             once one is joined, it's "here".
  * LAN      a Stump that joined the same router as the phone: found by
             asking every address of the local /24.

Probing must not change anything on the node. /rrc/poll would make the
phone a chat user (everyone sees "✓ guest-…"), so it's never used here.
Requests, in order:

  GET /node.json    name, lxmf, version, release, ap_ip, chain (null or the
                    /chain.json object), features. After 1.0.0-beta.2; an
                    older node answers it with its home page (HTML), so
                    anything not JSON falls through to the next request.
  GET /chain.json   any 1.0.0-beta.2 node; {"enabled": …} marks a Stump
  GET /files.json, /billboard.json   older nodes, when they offer them

How good a link is ("bars", 0-3):
  signal     the hotspot's RSSI from the scan
  steadiness a few small round trips: median time and how many were lost
  LoRa       the SNR of the last packet heard from the node, and its hops
"""
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from .stump_web import _attr

PROBE_TIMEOUT_MS = 1500
PORTS = (80, 8080)        # a Stump on a computer may serve on 8080 (CLIENT_QUICKSTART, Stumps on a computer)
SWEEP_TIMEOUT_MS = 700
SWEEP_WORKERS = 48
STEADY_SAMPLES = 5


def _get(http, url, timeout_ms):
    """-> (status, parsed JSON dict or None, elapsed ms)"""
    t = time.monotonic()
    try:
        r = http.request("GET", url, "{}", None, timeout_ms)
        status = int(_attr(r, "status"))
        raw = _attr(r, "body")
        body = bytes(raw) if raw is not None else b""
    except Exception:
        return -1, None, (time.monotonic() - t) * 1000
    ms = (time.monotonic() - t) * 1000
    data = None
    if status == 200 and body[:1] in (b"{", b"["):
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = None
    return status, data, ms


def _hash(v):
    return v.lower() if isinstance(v, str) and len(v) == 32 and all(c in "0123456789abcdefABCDEF" for c in v) else None


def _chain_summary(c):
    if not isinstance(c, dict) or not c.get("enabled"):
        return {"enabled": False, "role": None, "below": 0}
    below = c.get("below")
    return {"enabled": True, "role": c.get("role") if c.get("role") in ("root", "member") else None,
            "below": len(below) if isinstance(below, list) else 0}


def identify(http, base, timeout_ms=PROBE_TIMEOUT_MS):
    """Is there a Stump at `base`? -> dict or None. Changes nothing on the node."""
    status, data, ms = _get(http, base + "/node.json", timeout_ms)
    if status < 0:
        return None                                  # nothing answered: no need to ask twice
    if isinstance(data, dict) and any(k in data for k in ("name", "lxmf", "release", "ap_ip", "features")):
        # Any of its keys may be null (a node without a name, or with LoRa off): still /node.json.
        feats = data.get("features")
        return {"base": base, "via": "/node.json", "name": str(data.get("name") or "")[:64] or None,
                "version": str(data["version"])[:32] if data.get("version") else None,
                "release": str(data["release"])[:32] if data.get("release") else None,
                "lxmf": _hash(data.get("lxmf")), "ap_ip": data.get("ap_ip") if isinstance(data.get("ap_ip"), str) else None,
                "chain": _chain_summary(data.get("chain")),        # null unless chained, else the /chain.json object
                "features": [str(f) for f in feats][:12] if isinstance(feats, list) else None,
                "radio": data.get("radio") if isinstance(data.get("radio"), dict) else None,
                "first_ms": ms}
    status, data, ms2 = _get(http, base + "/chain.json", timeout_ms)
    if isinstance(data, dict) and "enabled" in data:
        return {"base": base, "via": "/chain.json", "name": None, "version": None, "release": None, "features": None, "lxmf": None,
                "ap_ip": data.get("ap_ip") if isinstance(data.get("ap_ip"), str) else None,
                "chain": _chain_summary(data), "first_ms": ms2}
    for path, key in (("/files.json", "files"), ("/billboard.json", "posts")):      # older nodes
        status, data, ms3 = _get(http, base + path, timeout_ms)
        if isinstance(data, dict) and key in data:
            return {"base": base, "via": path, "name": None, "version": None, "release": None, "features": None, "lxmf": None, "ap_ip": None,
                    "chain": _chain_summary(None), "first_ms": ms3}
    return None


def steadiness(http, url, samples=STEADY_SAMPLES, timeout_ms=PROBE_TIMEOUT_MS):
    """A few small GETs, one after the other. -> {"median_ms", "lost", "samples"}"""
    times, lost = [], 0
    for _ in range(samples):
        status, _, ms = _get(http, url, timeout_ms)
        if status == 200:
            times.append(ms)
        else:
            lost += 1
    return {"median_ms": round(statistics.median(times)) if times else None, "lost": lost, "samples": samples}


def _has_port(base):
    host = base.split("://", 1)[-1].split("/", 1)[0]
    return ":" in host


def probe(http, base, samples=STEADY_SAMPLES):
    """identify() plus steadiness, with bars. -> dict, {"stump": False} when nothing Stump-like answers.
    An address without a port is tried on 80, then on 8080 (a Stump on a computer)."""
    info = identify(http, base)
    if not info and not _has_port(base):
        info = identify(http, base.rstrip("/") + ":8080")
    if not info:
        return {"base": base, "stump": False}
    st = steadiness(http, base + info["via"], samples)
    info.update(st)
    info["stump"] = True
    info["steady_bars"] = steady_bars(st["median_ms"], st["lost"], st["samples"])
    return info


# ------------------------------------------------------------------ bars
def signal_bars(rssi):
    """Wi-Fi RSSI (dBm) -> 0..3"""
    if rssi is None:
        return None
    return 3 if rssi >= -60 else 2 if rssi >= -72 else 1 if rssi >= -85 else 0


def steady_bars(median_ms, lost, samples):
    if not samples or median_ms is None:
        return 0
    loss = lost / samples
    if loss == 0 and median_ms < 150:
        return 3
    if loss <= 0.2 and median_ms < 400:
        return 2
    if loss < 0.6:
        return 1
    return 0


def lora_bars(snr):
    """SNR (dB) of the last packet heard -> 0..3. SF8 decodes down to about -10 dB."""
    if snr is None:
        return None
    return 3 if snr >= 5 else 2 if snr >= -3 else 1 if snr >= -10 else 0


def overall(*bars):
    """The weakest known part of the link decides."""
    known = [b for b in bars if b is not None]
    return min(known) if known else None


# ------------------------------------------------------------------ the LAN
def lan_hosts(own_ip, prefix):
    """The addresses to ask: the phone's own /24 (or its smaller subnet), minus itself."""
    try:
        parts = [int(x) for x in own_ip.split(".")]
        assert len(parts) == 4 and all(0 <= x <= 255 for x in parts)
    except Exception:
        return []
    prefix = max(24, int(prefix or 24))
    size = 1 << (32 - prefix)
    me = parts[3]
    start = (me // size) * size
    base = ".".join(map(str, parts[:3]))
    return [f"{base}.{h}" for h in range(start + 1, start + size - 1) if h != me]


def sweep(http, own_ip, prefix, skip=(), timeout_ms=SWEEP_TIMEOUT_MS, workers=SWEEP_WORKERS, samples=3):
    """Every Stump on the local network. -> list of probe() results, steadiest first."""
    hosts = [h for h in lan_hosts(own_ip, prefix) if h not in set(skip)]
    bases = [f"http://{h}" if p == 80 else f"http://{h}:{p}" for h in hosts for p in PORTS]

    def ask(base):
        try:
            return identify(http, base, timeout_ms)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = [r for r in pool.map(ask, bases) if r]
    out = []
    for info in found:
        st = steadiness(http, info["base"] + info["via"], samples)
        info.update(st)
        info["stump"] = True
        info["steady_bars"] = steady_bars(st["median_ms"], st["lost"], st["samples"])
        out.append(info)
    out.sort(key=lambda i: (-i["steady_bars"], i["median_ms"] or 1e9))
    return out


# ------------------------------------------------------------------ Stumps that are just SSIDs
DEFAULT_SSID = "LaBuche-Stump.web.app"        # captive_portal.DEFAULT_SSID


def looks_like_stump(ssid, known=()):
    """From a scan: a hotspot we joined as a Stump before, the firmware's default name,
    or a name that says so. Anything else is only "maybe"."""
    s = (ssid or "").strip()
    if not s:
        return "no"
    if s in set(known) or s == DEFAULT_SSID:
        return "yes"
    return "likely" if "stump" in s.lower() else "maybe"
