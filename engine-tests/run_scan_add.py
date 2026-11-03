"""A Stump added by its address: its QR code (Stump 1.0.0-beta.51's /address) or typed.

    python3 run_scan_add.py

  * what a QR code or a paste gives is read: the plain 32 characters, <…>,
    a link like lxmf://<address>; anything else is refused;
  * adding puts it in the Stumps list at once (named by its short address,
    "<9b5c4744>", until its beacon says its name), and asks the network for
    it: the same way in as a Stump heard by itself (a path request, its
    announce, its beacon), so its name, its Wi-Fi side and verification
    (on opening it) follow as for any Stump;
  * adding it again changes nothing; a hidden one comes back; a blocked
    address and FireFly's own are refused.
"""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
import RNS
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

LX = "9b5c4744" + "a1" * 12
UP = LX.upper()
for text, want in [(LX, LX), (UP, LX), (f"<{LX}>", LX), (f"  {LX}\n", LX), (f"lxmf://{LX}", LX),
                   (f"lxmf://{LX}?name=LaBuche", LX), (f"lxma://{LX}:abcdef", LX), (LX[:16] + " " + LX[16:], LX),
                   (LX[:31], None), (LX + "0", None), ("hello", None), ("", None), (None, None),
                   ("https://example.com/" + LX, None), ("zz" * 16, None)]:
    got = stump.address_from_text(text)
    check(f"read {text!r:.50}", got == want, got)

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-scan-"), None, None, L())
c = api._core
asked = []
real_request = RNS.Transport.request_path
RNS.Transport.request_path = lambda h, *a, **k: asked.append(h.hex())

rows = lambda: json.loads(api.stump_nodes())
row = lambda: next((r for r in rows() if r.get("lxmf") == LX), None)

r = json.loads(api.stump_add_address(f"<{LX}>"))
check("added: a new Stump", r.get("key") == "mesh:" + LX and r.get("new") is True, r)
check("...in the Stumps list at once, named by its short address", row() is not None and row()["name"] == f"<{LX[:8]}>", row())
check("...the network is asked for it (its announce, without waiting)", LX in asked, asked)
check("...not 'answering' yet", row()["alive"] is False, row())
check("...nothing sent to it, nothing opened", "mesh:" + LX not in c.sessions)

# Its announce comes back (the path request's answer): FireFly asks for its beacon, as for any Stump.
ident = RNS.Identity()
dest = RNS.Destination.hash(ident, "lxmf", "delivery")
LX2 = dest.hex()
asked.clear()
api.stump_add_address(LX2)
c._on_delivery_announce(dest, ident, None)
check("its announce: its Stump beacon is asked for, as for any Stump",
      stump.beacon_hash_for(ident).hex() in asked, asked)
c._on_stump_beacon(LX2, "LaBuche", "1.0.0-beta.51", ["http://192.168.4.1"], boot="abc123")
r2 = next((r for r in rows() if r.get("lxmf") == LX2), None)
check("its beacon: its real name replaces the short address, one row", r2 and r2["name"] == "LaBuche"
      and sum(1 for r in rows() if r.get("lxmf") == LX2) == 1, r2)
check("...and heard (its beacon counts as hearing it)", r2.get("last_seen") and time.time() - r2["last_seen"] < 10, r2)

# Already known (its identity recalled): the beacon is asked for at once.
ident3 = RNS.Identity()
d3 = RNS.Destination(ident3, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
RNS.Identity.remember(None, d3.hash, ident3.get_public_key(), None)
asked.clear()
api.stump_add_address(d3.hash.hex())
check("an address whose identity is known: its beacon asked for at once",
      stump.beacon_hash_for(ident3).hex() in asked, asked)

r = json.loads(api.stump_add_address(LX))
check("added again: not new, still one row", r.get("new") is False and sum(1 for x in rows() if x.get("lxmf") == LX) == 1, r)
api.stump_hide("mesh:" + LX)
check("(hidden)", row() is None)
api.stump_add_address(LX)
check("a hidden one, added again: back in the list", row() is not None)

check("garbage: refused, with why", "not an LXMF address" in json.loads(api.stump_add_address("hello")).get("error", ""))
check("FireFly's own address: refused", "own" in json.loads(api.stump_add_address(c.address)).get("error", ""))
BL = "b1" * 16
c.blocked.add(BL) if isinstance(c.blocked, set) else None
if isinstance(c.blocked, set):
    check("a blocked address: refused", "blocked" in json.loads(api.stump_add_address(BL)).get("error", ""))
check("Chats' Add address reads a scanned code too", api.address_from_text(f"lxmf://{UP}") == LX
      and api.address_from_text("nope") == "")

RNS.Transport.request_path = real_request
print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
