"""Network › Propagation node: one On/Off switch (Nov 2026).

    python3 run_prop_switch.py

On: automatic (a node picked by hand is kept), and messages for people out of reach are left
there. Off: no node, nothing left there. Back On: automatic again.
"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
from firefly import api

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  ({str(detail)[:300]})" if detail and not ok else ""))
    fails += 0 if ok else 1

class L:
    def onEvent(self, s): pass
api.start(tempfile.mkdtemp(prefix="ff-prop-"), None, None, L())
c = api._core
st = lambda: (c.settings["propagation_mode"], c.settings["fallback_to_propagation"])
check("by default: on (automatic, and leaving messages there)", st() == ("auto", True), st())
check("Off: no node, nothing left there", api.propagation_set(False) == "off" and st() == ("off", False)
      and c.settings["propagation_node"] is None, st())
check("On: automatic again, and leaving messages there", api.propagation_set(True) == "auto" and st() == ("auto", True), st())
node = "ab" * 16
api.use_propagation_node(node)
check("(a node picked by hand)", c.settings["propagation_mode"] == "manual", st())
api.propagation_set(True)
check("On with a node picked by hand: kept", c.settings["propagation_mode"] == "manual"
      and c.settings["fallback_to_propagation"] is True, (st(), c.settings.get("propagation_node")))
api.propagation_set(False)
api.propagation_set(True)
check("...switched Off and On again: automatic", st() == ("auto", True), st())
print("ALL PASS" if not fails else f"{fails} FAILED")
os._exit(1 if fails else 0)
