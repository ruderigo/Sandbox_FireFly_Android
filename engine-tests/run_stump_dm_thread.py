"""A DM to a Stump comes back in the same thread, not as someone else (Nov 12; Stump 1.0.0-beta.64).

    python3 run_stump_dm_thread.py

A Stump answers DMs under its name as typed ("LaBuche-Stump-eK0ms"); FireFly knew it by its
nick ("LaBuche-Stump-eK", 16 characters at most), so the answer opened a new thread. Now any form
of the Stump's own name is that Stump; a person's nick that starts the same is still themselves.
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

NAME = "LaBuche-Stump-eK0ms"
check("the Stump's nick: cleaned, 16 at most", stump.stump_nick(NAME) == "LaBuche-Stump-eK")
check("its name as typed is the Stump", stump.is_stump_itself(NAME, NAME))
check("its nick is the Stump", stump.is_stump_itself("LaBuche-Stump-eK", NAME))
check("a name with a space that cleans to its nick is the Stump", stump.is_stump_itself("LaBuche Stump eK0ms", NAME))
check("a person whose nick starts the same is not", not stump.is_stump_itself("LaBuche-Stump-e2", NAME)
      and not stump.is_stump_itself("LaBuche", NAME) and not stump.is_stump_itself("alice", NAME))
check("a short name: itself only", stump.is_stump_itself("Laptop", "Laptop") and not stump.is_stump_itself("Laptop2", "Laptop"))

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-sdm-"), None, None, L())
c = api._core
LX = "ab" * 16
K = "mesh:" + LX
c.store.upsert_stump_node(K, "mesh", LX, name=NAME, last_seen=time.time())
sess = c.session(K)
sess.pipe.send = lambda line, control=False: 1
threads = lambda: sorted(t["nick"] for t in c.store.dm_threads(K))

sess.send_dm("LaBuche-Stump-eK", "hello Stump")
sess._incoming_dm(NAME, "hello! I'm the Stump")
check("its answer under its name as typed: in the same thread", threads() == ["LaBuche-Stump-eK"], threads())
thread = json.loads(api.stump_dm_thread(K, "LaBuche-Stump-eK"))
check("...both lines in it", [d["body"] for d in thread] == ["hello Stump", "hello! I'm the Stump"], [d["body"] for d in thread])
sess._incoming_dm("LaBuche-Stump-e2", "I'm a person")
check("a person whose nick starts the same: their own thread", threads() == ["LaBuche-Stump-e2", "LaBuche-Stump-eK"], threads())

# No thread yet: the Stump writing first goes under its nick; then FireFly's answer joins it.
LX2 = "cd" * 16; K2 = "mesh:" + LX2
c.store.upsert_stump_node(K2, "mesh", LX2, name="Bûche du parc Lafontaine", last_seen=time.time())
s2 = c.session(K2); s2.pipe.send = lambda line, control=False: 1
s2._incoming_dm("Bûche du parc Lafontaine", "welcome")
t2 = sorted(t["nick"] for t in c.store.dm_threads(K2))
check("the Stump writing first: under its nick", t2 == [stump.stump_nick("Bûche du parc Lafontaine")], t2)
s2._incoming_dm(stump.stump_nick("Bûche du parc Lafontaine"), "and again")
check("...its nick next time: same thread", len(c.store.dm_threads(K2)) == 1)

# /names since Stump 1.0.0-beta.64 marks ops and mods: @alice, %bob. The people are alice and bob.
check("/names marks: @op, %mod, ~verified are the bare nicks", [stump.bare_nick(n) for n in ["@alice", "%bob", "~carol", "dave"]]
      == ["alice", "bob", "carol", "dave"])
sess.room = "main"
sess._handle(stump.parse_line("#main: @alice, %bob, ~carol, dave"))
users = json.loads(api.stump_view(K, "main")).get("users")
check("...the people list FireFly keeps (for DMs): alice, bob, carol, dave", users == ["alice", "bob", "carol", "dave"], users)
lines = [l["body"] for l in json.loads(api.stump_view(K, "main"))["lines"]]
check("...the /names line shown keeps the marks", any("@alice" in b and "%bob" in b for b in lines), lines[-3:])

print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
