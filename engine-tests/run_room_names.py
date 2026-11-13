"""Everyone in the room, at once (Nov 13; Stump 1.0.0-beta.69).

    python3 run_room_names.py

In #lora-mesh, people on other Stumps (nick@stump) are only in /names: a Wi-Fi poll's "users"
lists this Stump's people, and each poll overwrote the list. Now FireFly asks /names on
entering a room (answer shown), keeps it per room, merges it with each poll's list, and over
Wi-Fi asks again every minute, quietly. Over LoRa: on entry only.
"""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-names-"), None, None, L())
c = api._core
LX = "ef" * 16; K = "mesh:" + LX
c.store.upsert_stump_node(K, "mesh", LX, name="Bûche", last_seen=time.time())
sess = c.session(K)
sent = []
sess.pipe.send = lambda line, control=False: sent.append(line) or 1
users = lambda room: json.loads(api.stump_view(K, room)).get("users")
lines = lambda room: [l["body"] for l in json.loads(api.stump_view(K, room))["lines"]]

# ---- LoRa: entering a room asks /names once
sess.room = "main"
sess._set_room("lora-mesh", "moved")
check("entering #lora-mesh: /names sent at once", sent.count("/names") == 1, sent)
sess._handle(stump.parse_line("#lora-mesh: @alice, bob@parc, carol@gare"))
check("...everyone, other Stumps included", users("lora-mesh") == ["alice", "bob@parc", "carol@gare"], users("lora-mesh"))
check("...the answer is shown", any("bob@parc" in b for b in lines("lora-mesh")), lines("lora-mesh")[-3:])
sess._names_for_room()
check("over LoRa: not asked again while in the room", sent.count("/names") == 1, sent)

# ---- a poll (Wi-Fi) lists this Stump's people only: they're merged, not a replacement
sess.on_http_poll({"room": "lora-mesh", "users": ["alice", "dave"], "messages": []})
check("a poll keeps the people on other Stumps", users("lora-mesh") == ["alice", "dave", "bob@parc", "carol@gare"],
      users("lora-mesh"))

# ---- Wi-Fi: again every minute, quietly
sess.pipe.kind = "wifi"
n_lines = len(lines("lora-mesh"))
sess.names_asked_at -= sess.NAMES_REFRESH_S + 1
sess._names_for_room()
check("over Wi-Fi: asked again after a minute", sent.count("/names") == 2, sent)
sess._handle(stump.parse_line("#lora-mesh: alice, carol@gare, erin@pont"))
check("...the refresh isn't shown as a line", len(lines("lora-mesh")) == n_lines, lines("lora-mesh")[-3:])
check("...someone gone, someone new", users("lora-mesh") == ["alice", "dave", "carol@gare", "erin@pont"], users("lora-mesh"))
sess._names_for_room()
check("...not again before the minute", sent.count("/names") == 2, sent)

# ---- another room: its own list, asked on entry
sess._set_room("main")
check("entering #main: /names again", sent.count("/names") == 3, sent)
sess._handle(stump.parse_line("#main: frank"))
sess.on_http_poll({"room": "main", "users": ["frank", "gina"], "messages": []})
check("#main's list: no one from #lora-mesh", users("main") == ["frank", "gina"], users("main"))

# ---- a poll that moves us: /names for the new room
sess.on_http_poll({"room": "lora-mesh", "users": ["alice"], "messages": []})
check("the poll moving us to #lora-mesh: /names asked", sent.count("/names") == 4, sent)

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
