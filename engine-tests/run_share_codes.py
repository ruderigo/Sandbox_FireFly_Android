"""Settings › Identity › Share (Nov 2026): FireFly's own QR codes, for every LXMF app.

    python3 run_share_codes.py

Each code FireFly shows is read back the way the other apps (and FireFly itself) read it:
the bare address (Sideband, NomadNet), lxma://<address>:<key> (Columba, MeshChatX) with a key
that matches the address, and the lxmf:// link.
"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
import RNS
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-share-"), None, None, L())
c = api._core
codes = json.loads(api.share_codes())
me = c.local.hash.hex()
check("the bare address: FireFly's, 32 characters (Sideband, NomadNet)", codes["bare"] == me and len(me) == 32, codes)
p = stump.parse_address_link(codes["lxma"])
check("lxma://: FireFly's address and its public key (Columba, MeshChatX)", p and p["address"] == me
      and p["key"] == c.identity.get_public_key() and p["scheme"] == "lxma", p)
check("...the key matches the address (what Columba and FireFly check)", stump.identity_for(me, p["key"]) is not None)
check("...and the address is the one LXMF computes from that key",
      RNS.Destination.hash(stump.identity_for(me, p["key"]), "lxmf", "delivery").hex() == me)
check("the link: lxmf://<address>", codes["link"] == "lxmf://" + me and stump.address_from_text(codes["link"]) == me)
check("...all three read back as FireFly's address", {stump.address_from_text(codes[k]) for k in ("bare", "lxma", "link")} == {me})
print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
