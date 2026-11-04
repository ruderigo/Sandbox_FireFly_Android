"""Every LXMF app's QR code (Nov 2026): FireFly can message them all.

    python3 run_lxmf_codes.py

  * lxma://<address>:<public key> (Columba, MeshChatX, the T-Deck LXMF Messenger): the
    key, hex or base64url, checked against the address and handed to Reticulum -- a person
    reachable at once, before any announce; a forged one refused;
  * the bare address (Sideband, NomadNet, Skywave), lxmf://<address>: read as before;
  * lxm:// paper messages (Sideband, any LXMF app): a whole message in a QR code, read by
    LXMF itself, arriving in its sender's conversation; a duplicate, one for someone else
    and garbage each said so.
"""
import base64, json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
import RNS, LXMF
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-codes-"), None, None, L())
c = api._core
RNS.Transport.request_path = lambda *a, **k: None
chk = lambda t: json.loads(api.address_check(t))
add = lambda t, k: json.loads(api.address_add(t, k))

def new_id():
    i = RNS.Identity()
    return i, RNS.Destination.hash(i, "lxmf", "delivery").hex()

# --- lxma:// (Columba, MeshChatX, T-Deck)
i1, A1 = new_id()
code = f"lxma://{A1}:{i1.get_public_key().hex()}"
p = stump.parse_address_link(code)
check("lxma://<address>:<hex key>: address and key read", p["address"] == A1 and p["key"] == i1.get_public_key(), p)
r = chk(code)
check("...a person, reachable at once (no announce needed)", r["kind"] == "person" and r["reachable"], r)
r = add(code, "person")
check("...added: a contact in Chats, its key with Reticulum", r.get("peer") == A1 and r.get("reachable")
      and RNS.Identity.recall(bytes.fromhex(A1)) is not None, r)
t = time.time()
mid = api.send(A1, "hi Columba")
row = lambda: next((m for m in json.loads(api.messages(A1)) if m.get("id") == mid), {})
time.sleep(1.5)
check("...and a message to it goes out at once, never 'unknown peer' (before any announce)",
      mid and mid != -1 and time.time() - t < 5 and "unknown peer" not in str(row().get("reason") or ""), row())
i2, A2 = new_id()
b64 = base64.urlsafe_b64encode(i2.get_public_key()).decode().rstrip("=")
check("lxma:// with a base64url key too", chk(f"lxma://{A2}:{b64}")["kind"] == "person"
      and stump.parse_address_link(f"lxma://{A2}:{b64}")["key"] == i2.get_public_key())
check("LXMA:// in capitals", chk(f"LXMA://{A2.upper()}:{i2.get_public_key().hex()}")["kind"] == "person")
_, A3 = new_id()
r = chk(f"lxma://{A3}:{i1.get_public_key().hex()}")
check("a forged lxma:// (someone else's key): refused, not trusted", r["kind"] == "bad" and "not trusted" in r["error"], r)
r = chk(f"lxma://{A3}:zz")
check("...a broken key: refused", r["kind"] == "bad", r)
i4, A4 = new_id()
c._on_stump_beacon(A4, "LaBuche", "1.0.0-beta.53", [])
check("an lxma:// code of a Stump FireFly knows: the Stumps list", chk(f"lxma://{A4}:{i4.get_public_key().hex()}")["kind"] == "stump")

# --- the others, as before
_, A5 = new_id()
check("the bare address (Sideband, NomadNet, Skywave): asked, Stump suggested", chk(A5)["kind"] == "ask")
check("lxmf://<address>: asked, person suggested", chk(f"lxmf://{A5}")["suggest"] == "person")

# --- lxm:// paper messages (Sideband, any LXMF app)
sender_id = RNS.Identity()
sender = RNS.Destination(sender_id, RNS.Destination.IN, RNS.Destination.SINGLE, "lxmf", "delivery")
to_me = RNS.Destination(c.identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
def paper(dest, text):
    m = LXMF.LXMessage(dest, sender, text, "", desired_method=LXMF.LXMessage.PAPER)
    m.pack()
    return m.as_uri()
uri = paper(to_me, "hello on paper")
check("a paper message is recognised as one", chk(uri)["kind"] == "paper")
r = json.loads(api.paper_message(uri))
check("...read: for me, delivered, from its sender", r["result"] == "delivered" and r["peer"] == sender.hash.hex(), r)
msgs = lambda: json.loads(api.messages(sender.hash.hex()))
t = time.time()
while time.time() - t < 5 and not any(m.get("content") == "hello on paper" for m in msgs()):
    time.sleep(0.2)
check("...in its sender's conversation, like any message", any(m.get("content") == "hello on paper" for m in msgs()),
      [m.get("content") for m in msgs()])
r = json.loads(api.paper_message(uri))
check("the same one again: a duplicate, not stored twice", r["result"] == "duplicate"
      and sum(1 for m in msgs() if m.get("content") == "hello on paper") == 1, r)
other_id = RNS.Identity()
to_other = RNS.Destination(other_id, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
r = json.loads(api.paper_message(paper(to_other, "not yours")))
check("one for someone else: says so", r["result"] == "not_for_you", r)
check("garbage after lxm://: bad", json.loads(api.paper_message("lxm://notamessage"))["result"] == "bad")
check("LXM:// in capitals is read too", json.loads(api.paper_message("LXM://" + paper(to_me, "caps")[6:]))["result"] == "delivered")

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
