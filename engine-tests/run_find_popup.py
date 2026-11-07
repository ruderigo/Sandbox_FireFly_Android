"""The Find Stumps popup (Nov 2026): find the Stumps on this Wi-Fi, tick some, add them at once.

    python3 run_find_popup.py

  * the quick search (STUMP?) lists the Stumps that answer and aren't in the list yet;
    one already in the list isn't repeated (it's followed to its new address instead);
  * adding the ticked ones puts them in the Stumps list, under their names, none opened
    (each greets itself as usual); an unticked one stays out;
  * searching again: nothing new.
"""
import json, os, sys, tempfile, time
os.environ["FIREFLY_BROADCAST"] = "127.0.0.41,127.0.0.42,127.0.0.43"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
sys.path.insert(0, HERE)
from fake_stump import FakeRRC, rns_verify, serve_http, serve_udp
from firefly import api

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

stumps = {}
for n, (ip, name) in enumerate([("127.0.0.41", "Souche"), ("127.0.0.42", "Racine"), ("127.0.0.43", "Tronc")]):
    rrc = FakeRRC(rns_verify); rrc.enable_hello(); rrc.node_name = name
    port = 47810 + n
    serve_http(port, rrc, host=ip)
    base = f"http://{ip}:{port}"
    serve_udp(ip, {"stump": 1, "name": name, "lxmf": rrc.node_lxmf, "release": "1.0.0-beta.55",
                   "http": [base + "/"], "here": base + "/"})
    stumps[name] = (base, rrc.node_lxmf)

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-find-"), None, None, L())
c = api._core
rows = lambda: json.loads(api.stump_nodes())
names = lambda: sorted(r.get("name") or "" for r in rows())

# Tronc is already in the list.
api.stump_connect_wifi(stumps["Tronc"][0])
c.store.upsert_stump_node("wifi:" + stumps["Tronc"][0], "wifi", stumps["Tronc"][0], name="Tronc", lxmf=stumps["Tronc"][1])

t = time.time()
found = json.loads(api.find_new_stumps("quick"))
check("the quick search: the two new Stumps, about a second", sorted(f["name"] for f in found) == ["Racine", "Souche"]
      and time.time() - t < 4, (found, time.time() - t))
check("...each with what the popup shows (name, address, LXMF, release)", all(f["base"] and f["lxmf"] and f["release"] for f in found), found)
check("...the one already in the list isn't repeated", not any(f["name"] == "Tronc" for f in found))

ticked = [f for f in found if f["name"] == "Souche"]
r = json.loads(api.stumps_add_found(json.dumps(ticked)))
check("adding the ticked one: in the list, under its name", r.get("added") == 1 and "Souche" in names(), (r, names()))
check("...the unticked one stays out", "Racine" not in names(), names())
key = r["keys"][0]
def greeted():
    t0 = time.time()
    while time.time() - t0 < 10:
        sess = c.sessions.get(key)
        if sess is not None and sess.verify["state"] == "ok":
            return True
        time.sleep(0.2)
    return False
check("...greeting itself as usual (/hello, verified), nobody opened it", greeted(),
      c.sessions.get(key) and c.sessions[key].verify)

found = json.loads(api.find_new_stumps("quick"))
check("searching again: only the one not added", [f["name"] for f in found] == ["Racine"], found)
r = json.loads(api.stumps_add_found(json.dumps(found)))
check("adding it too", r.get("added") == 1 and "Racine" in names(), names())
check("searching again: nothing new", json.loads(api.find_new_stumps("quick")) == [])
check("three Stumps in the list, one row each", names() == ["Racine", "Souche", "Tronc"], names())

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
