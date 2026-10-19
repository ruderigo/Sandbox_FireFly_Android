"""A private message that came over LoRa, read from the Stump's Wi-Fi side (field report, Oct 19).

    python3 run_dm_sides.py

A Stump known over LoRa and Wi-Fi is one row in the Stumps tab and two
entries underneath. A DM to the phone's old nick ("rods-cell") arrived over
LoRa and was stored under the LoRa entry; the row's badge counted it, but
the row opens the Wi-Fi side, whose DM list didn't show it. Now one Stump's
private messages are one conversation per person, whichever way they came,
and a reply goes by the side that can reach the Stump.
"""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
sys.path.insert(0, HERE)
from fake_stump import FakeRRC, rns_verify, serve_http
from firefly import api

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1
def wait(cond, secs=15):
    t = time.time()
    while time.time() - t < secs:
        if cond(): return True
        time.sleep(0.3)
    return False

LX = "dd" * 16
rrc = FakeRRC(rns_verify); rrc.node_lxmf = LX
serve_http(47670, rrc)
class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-dmsides-"), None, None, L())
c = api._core
c.store.upsert_stump_node("mesh:" + LX, "mesh", LX, name="macOS", last_seen=time.time())
wkey = api.stump_connect_wifi("http://127.0.0.1:47670")
check("the Wi-Fi side is up and knows the Stump's identity",
      wait(lambda: (c.store.stump_node(wkey) or {}).get("lxmf") == LX and json.loads(api.stump_view(wkey)).get("online") == 1))

# (The fake Stump's alice greets every newcomer with a DM: count from what's there.)
unread = lambda: next(r for r in json.loads(api.stump_nodes()) if r.get("group") == LX)["unread_dms"]
wait(lambda: unread() >= 1, 5)
before = unread()
# The DM to the old nick, as it arrives over LoRa: "[DM] <rod@LaBuche>: …" on the LoRa entry.
c.session("mesh:" + LX)._incoming_dm("rod@LaBuche", "are you there, rods-cell?")
row = next(r for r in json.loads(api.stump_nodes()) if r.get("group") == LX)
check("the Stumps row: one row, opening over Wi-Fi, one more unread DM",
      row["key"] == wkey and row["unread_dms"] == before + 1, (row["key"], row["unread_dms"], before))
threads = json.loads(api.stump_view(wkey))["threads"]
check("the Wi-Fi side's DM list shows the conversation, unread",
      any(t["nick"] == "rod@LaBuche" and t["unread"] == 1 for t in threads), threads)
msgs = json.loads(api.stump_dm_thread(wkey, "rod@LaBuche"))
check("opening it shows the message", any(m["body"] == "are you there, rods-cell?" for m in msgs), msgs)
check("...and reading it clears it from the badge", unread() == before, (unread(), before))

# A message that comes over Wi-Fi joins the same conversation, in order.
rrc.inbox.setdefault("web:127.0.0.1", []).append({"id": rrc._id(), "ts": time.time(), "nick": "rod@LaBuche",
                                                  "body": "now over Wi-Fi", "kind": "dm"})
check("over Wi-Fi: same conversation, after the LoRa one",
      wait(lambda: [m["body"] for m in json.loads(api.stump_dm_thread(wkey, "rod@LaBuche"))][-2:] ==
           ["are you there, rods-cell?", "now over Wi-Fi"]),
      [m["body"] for m in json.loads(api.stump_dm_thread(wkey, "rod@LaBuche"))])
check("the LoRa side shows the same conversation (opened from the notification)",
      [m["body"] for m in json.loads(api.stump_dm_thread("mesh:" + LX, "rod@LaBuche"))][-1] == "now over Wi-Fi")

# Replying from the LoRa side with no radio: it goes over Wi-Fi.
api.stump_send_dm("mesh:" + LX, "alice", "here, as RodRod")
check("a reply from the LoRa side with no radio goes over Wi-Fi",
      wait(lambda: any(d.get("body") == "here, as RodRod" for d in rrc.inbox.get("alice", []))), rrc.inbox.get("alice"))
print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
