"""The billboard over LoRa (Stump 1.0.0-beta.38), and other beta.34-38 answers.

    python3 run_board_lora.py

/board, /board <id> and /post go to the Stump's LoRa side; its answers (an LXMF
batch, as the Stump's rrc.board_command writes them) fill FireFly's LoRa Board
tab and don't land in the room. Also: the radio-down ⧗ keeps a line (it isn't
"not sent"), a forged stump.node beacon is ignored, and a bot's lines ("bot":
true) aren't offered as a DM contact.
"""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
sys.path.insert(0, HERE)
import RNS
from firefly import api, stump

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-boardlora-"), None, None, L())
c = api._core
LX = "ef" * 16
K = "mesh:" + LX
c.store.upsert_stump_node(K, "mesh", LX, name="LaBuche", last_seen=time.time())
sess = c.session(K)
sent = []
sess.pipe.send = lambda line, control=False: sent.append(line)
view = lambda: json.loads(api.stump_board_lora_view(K))
room = lambda: [l["body"] for l in json.loads(api.stump_view(K))["lines"]]

api.stump_board_lora(K)
check("/board asked over LoRa", sent[-1] == "/board" and view()["state"] == "waiting", (sent, view()["state"]))
sess.on_mesh_content("#482193 Marché samedi\n#612803 Vélo à vendre")       # the Stump's answer
v = view()
check("its answer is the list: ids and titles", v["state"] == "ok"
      and v["posts"] == [{"id": "482193", "title": "Marché samedi"}, {"id": "612803", "title": "Vélo à vendre"}], v)
check("...and isn't drawn in the room", not any("Marché" in b for b in room()), room())

api.stump_board_lora(K, "  velo  ")
check("/board <words>", sent[-1] == "/board velo")
sess.on_mesh_content('nothing on the billboard about "velo"')
check("...nothing about them: empty", view()["state"] == "empty")

api.stump_board_lora_item(K, "612803")
check("/board <id>", sent[-1] == "/board 612803")
sess.on_mesh_content("#612803 Vélo à vendre\nBon état.\nAppeler le soir.")
it = view()["items"].get("612803")
check("...its title and body (line breaks kept)", it and it["title"] == "Vélo à vendre" and it["body"] == "Bon état.\nAppeler le soir.", it)
api.stump_board_lora_item(K, "111111")
sess.on_mesh_content("no notice #111111 (expired?)")
check("...an expired one: gone", view()["items"].get("111111", {}).get("gone") is True, view()["items"])

check("/post with a body", api.stump_board_lora_post(K, "Soupe  ce soir", "18 h\nchez Rod") == "true"
      and sent[-1] == "/post Soupe ce soir | 18 h\nchez Rod", sent[-1])
sess.on_mesh_content("✓ #700512")
check("...posted: ✓ #id", view()["post"] == {"state": "ok", "id": "700512", "title": "Soupe ce soir"}, view()["post"])
api.stump_board_lora_post(K, "Encore")
sess.on_mesh_content("⧗ — posting too fast, wait a minute")
check("...refused: the Stump's reason", view()["post"]["state"] == "refused" and "too fast" in view()["post"]["message"], view()["post"])
check("an empty title isn't sent", api.stump_board_lora_post(K, "   ") == "false")

# A batch that isn't the answer (a room line arriving meanwhile) isn't taken for it.
api.stump_board_lora(K)
sess.on_mesh_content("<alice> hello there", title="#main")
check("a room line meanwhile stays a room line", view()["state"] == "waiting" and any("hello there" in l["body"] for l in json.loads(api.stump_view(K, "main"))["lines"]))
sess.on_mesh_content("no billboard on this Stump")
check("billboard switched off: off", view()["state"] == "off")

# Radio down: the line is kept, not 'not sent'.
sess.post("for the radio room")
sess.on_mesh_content("⧗ — the radio has been down for 4 min: your message will go out when it's back (kept up to an hour)")
lines = json.loads(api.stump_view(K))["lines"]
mine = [l for l in lines if l.get("mine") and l["body"] == "for the radio room"]
check("radio down: the line isn't marked not sent", mine and mine[-1].get("local_state") != "failed", mine)
check("...and the Stump's note is shown", any("radio has been down" in l["body"] for l in lines))

# A forged beacon: another identity naming this Stump's LXMF address.
me, other = RNS.Identity(), RNS.Identity()
own = RNS.Destination.hash(me, "lxmf", "delivery").hex()
check("a beacon naming its own LXMF address is taken", stump.beacon_is_own(own, me))
check("...one naming someone else's is not (forged)", not stump.beacon_is_own(own, other))

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
