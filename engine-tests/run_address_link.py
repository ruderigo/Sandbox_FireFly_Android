"""An address scanned, typed or tapped: the Stumps list or Chats, decided at once (Stump 1.0.0-beta.52).

    python3 run_address_link.py

The order agreed with the Stump team:
  1. the code says so: lxmf://<address>?stump=<name>&key=<public key> (beta.52), its key
     checked against the address (a faked code is refused), and handed to Reticulum, so the
     Stump can be written to before any announce;
  2. a Stump FireFly already knows;
  3. a Stump on this Wi-Fi that proves it's that one (STUMP?, then its signed GET /hello);
  4. else the user is asked, with a suggestion (Stump for the bare address, person for a link).
And the Chats side: a Stump added from Chats goes to the Stumps list, never into a plain chat;
an open chat whose address turns out to be a Stump's is pointed to it (peer_stump).
"""
import base64, json, os, sys, tempfile, time
os.environ["FIREFLY_BROADCAST"] = "127.0.0.21"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
sys.path.insert(0, HERE)
import RNS
from fake_stump import FakeRRC, rns_verify, serve_http, serve_udp
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

def b64(key):
    return base64.urlsafe_b64encode(key).decode().rstrip("=")

def new_id():
    i = RNS.Identity()
    return i, RNS.Destination.hash(i, "lxmf", "delivery").hex()

# --- reading the link
i1, A1 = new_id()
link = f"lxmf://{A1}?stump=B%C3%BBche%203&key={b64(i1.get_public_key())}"
p = stump.parse_address_link(link)
check("beta.52's link: the address, the name (UTF-8, %-encoded), the key",
      p["address"] == A1 and p["stump"] == "Bûche 3" and p["key"] == i1.get_public_key() and p["link"], p)
check("...the key matches the address", stump.identity_for(A1, p["key"]) is not None)
_, other = new_id()
check("...a key that isn't this address's: no", stump.identity_for(other, p["key"]) is None)
p = stump.parse_address_link(A1)
check("the bare address (beta.51): not a link, nothing said", not p["link"] and p["stump"] is None and p["key"] is None, p)
p = stump.parse_address_link(f"lxmf://{A1}?stump=&key=abc")
check("an empty name still says Stump; a short key is flagged", p["stump"] == "" and p["key"] is None and p["key_bad"], p)
check("the key alone (someone else's link): no Stump said", stump.parse_address_link(
      f"lxmf://{A1}?key={b64(i1.get_public_key())}")["stump"] is None)

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-link-"), None, None, L())
c = api._core
asked = []
RNS.Transport.request_path = lambda h, *a, **k: asked.append(h.hex())
chk = lambda t: json.loads(api.address_check(t))
add = lambda t, k: json.loads(api.address_add(t, k))
chats = lambda: {r["peer"] for r in json.loads(api.conversations())} | {r["hash"] for r in json.loads(api.peers())}
row = lambda h: next((r for r in json.loads(api.stump_nodes()) if r.get("lxmf") == h), None)

# --- 1. the link says it's a Stump
t = time.time()
r = chk(link)
check("1. the link: a Stump, at once, under its name, reachable",
      r["kind"] == "stump" and r["how"] == "link" and r["name"] == "Bûche 3" and r["reachable"] and time.time() - t < 0.5, r)
check("...nothing known about it before", RNS.Identity.recall(bytes.fromhex(A1)) is None)
r = add(link, "stump")
check("added: in the Stumps list under its name", r.get("kind") == "stump" and row(A1) and row(A1)["name"] == "Bûche 3", (r, row(A1)))
check("...its key is with Reticulum: it can be written to before any announce",
      r.get("reachable") and RNS.Identity.recall(bytes.fromhex(A1)) is not None)
check("...and its beacon asked for right away", stump.beacon_hash_for(i1).hex() in asked, asked)
check("...not in Chats", A1 not in chats())
c._on_stump_beacon(A1, "LaBuche", "1.0.0-beta.52", [], boot="aa11aa")
check("its beacon (signed) has the last word on the name", row(A1)["name"] == "LaBuche", row(A1))

forged = f"lxmf://{other}?stump=LaBuche&key={b64(i1.get_public_key())}"
r = chk(forged)
check("a code whose key isn't its address's: refused, not trusted", r["kind"] == "bad" and "not trusted" in r["error"], r)
check("...and can't be added either", "not trusted" in add(forged, "stump").get("error", ""))
check("...nothing added", row(other) is None)

# --- 2. already known
i2, A2 = new_id()
c._on_stump_beacon(A2, "Souche", "1.0.0-beta.52", [])
r = chk(A2)
check("2. the bare address of a Stump heard before: a Stump, at once, its name", r["kind"] == "stump" and r["how"] == "known"
      and r["name"] == "Souche", r)

# --- 3. on its Wi-Fi, proving it
rrc = FakeRRC(rns_verify); rrc.enable_hello()
A3 = rrc.node_lxmf
serve_http(47770, rrc, host="127.0.0.21")
serve_udp("127.0.0.21", {"stump": 1, "name": "Racine", "lxmf": A3, "release": "1.0.0-beta.52",
                         "http": ["http://127.0.0.21:47770/"], "here": "http://127.0.0.21:47770/"})
t = time.time()
r = chk(A3)
check("3. a Stump on this Wi-Fi, by its signed /hello: a Stump, about a second", r["kind"] == "stump" and r["how"] == "wifi"
      and r["name"] == "Racine" and time.time() - t < 3, (r, time.time() - t))
check("...only read: FireFly didn't greet it", not any(m == "POST" for _, m, _ in rrc.hello_log), rrc.hello_log)

rrc_f = FakeRRC(rns_verify); rrc_f.enable_hello(); rrc_f.hello_forge = True
serve_http(47771, rrc_f, host="127.0.0.22")
os.environ["FIREFLY_BROADCAST"] = "127.0.0.22"
serve_udp("127.0.0.22", {"stump": 1, "name": "Impostor", "lxmf": rrc_f.node_lxmf, "release": "1.0.0-beta.52",
                         "http": ["http://127.0.0.22:47771/"], "here": "http://127.0.0.22:47771/"})
r = chk(rrc_f.node_lxmf)
check("...one whose signature doesn't check out: not taken for it, the user is asked", r["kind"] == "ask", r)

# --- 4. otherwise: ask
_, A4 = new_id()
r = chk(A4)
check("4. unknown, bare address: ask, suggesting Stump", r["kind"] == "ask" and r["suggest"] == "stump", r)
r = chk(f"lxmf://{A4}")
check("...another app's link: ask, suggesting person", r["kind"] == "ask" and r["suggest"] == "person", r)
r = add(A4, "person")
check("the user says person: a contact, in Chats", r.get("kind") == "person" and r.get("peer") == A4 and A4 in chats(), r)
_, A5 = new_id()
add(A5, "stump")
check("the user says Stump: the Stumps list, short address for a name, not in Chats",
      row(A5) and row(A5)["name"] == f"<{A5[:8]}>" and A5 not in chats(), row(A5))
i6, A6 = new_id()
r = add(f"lxmf://{A6}?key={b64(i6.get_public_key())}", "person")
check("a person's link with a key: reachable at once too", r.get("reachable") is True, r)

# --- the Chats side
check("a chat with a person: no Stump to point to", api.peer_stump(A4) == "")
c._on_stump_beacon(A4, "Tronc", "1.0.0-beta.52", [])
check("...that address beacons as a Stump: the chat points to its Stumps entry", api.peer_stump(A4) == "mesh:" + A4)
check("...which is in the list", row(A4) is not None)
check("bad text: refused with why", chk("hello")["kind"] == "bad")
check("FireFly's own address: refused", chk(c.address)["kind"] == "bad")

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
