"""Test del parsing BGG e della logica di filtro, senza rete."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sync_bgg as s  # noqa: E402

COLLECTION_XML = """<items totalitems="3">
<item objecttype="thing" objectid="1" subtype="boardgame"><name sortindex="1">Alpha</name><yearpublished>2020</yearpublished>
 <stats minplayers="2" maxplayers="4" playingtime="60" numowned="1"><rating value="N/A"><average value="7.8"/><bayesaverage value="7.2"/></rating></stats>
 <status own="1"/><numplays>3</numplays></item>
<item objecttype="thing" objectid="2" subtype="boardgame"><name>Beta</name>
 <stats minplayers="1" maxplayers="1" playingtime="30"><rating value="N/A"><average value="0"/></rating></stats>
 <status own="0" wishlist="1"/><numplays>0</numplays></item>
<item objecttype="thing" objectid="3" subtype="boardgame"><name>Gamma</name>
 <stats minplayers="3" maxplayers="5" playingtime="90"><rating value="8"><average value="8.1"/></rating></stats>
 <status own="1"/><numplays>0</numplays></item>
</items>"""

THING_XML = """<items><item type="boardgame" id="1">
 <thumbnail>https://img/a.jpg</thumbnail>
 <link type="boardgamemechanic" id="1" value="Worker Placement"/><link type="boardgamemechanic" id="2" value="Dice Rolling"/>
 <link type="boardgamecategory" id="3" value="Economic"/>
 <poll name="suggested_numplayers" title="x" totalvotes="10">
  <results numplayers="3"><result value="Best" numvotes="8"/><result value="Recommended" numvotes="2"/><result value="Not Recommended" numvotes="0"/></results>
  <results numplayers="5+"><result value="Best" numvotes="0"/><result value="Recommended" numvotes="1"/><result value="Not Recommended" numvotes="9"/></results>
 </poll>
 <statistics><ratings><averageweight value="2.45"/></ratings></statistics></item></items>"""


def test_collection():
    games = s.parse_collection(ET.fromstring(COLLECTION_XML))
    assert [g["id"] for g in games] == [1, 3], "la wishlist (own=0) va esclusa"
    assert games[0]["avg_rating"] == 7.8 and games[0]["numplays"] == 3
    assert games[0]["minplayers"] == 2 and games[0]["playingtime"] == 60


def test_things():
    d = s.parse_things(ET.fromstring(THING_XML))[1]
    assert d["weight"] == 2.45
    assert d["mechanics"] == ["Worker Placement", "Dice Rolling"]
    assert d["categories"] == ["Economic"]
    assert d["best"] == [3], d["best"]
    assert d["thumbnail"] == "https://img/a.jpg"


def test_compact_text():
    games = s.parse_collection(ET.fromstring(COLLECTION_XML))
    for g in games:
        g.update(weight=None, mechanics=[], categories=[], best=[])
    games[0].update(weight=2.45, mechanics=["Worker Placement"], best=[3])
    txt = s.compact_text(games, "2026-10-31T10:00+00:00")
    lines = txt.strip().split("\n")
    assert len(lines) == 3 + 2
    assert lines[3].startswith("Gamma | 3-5 | 90 | ? | 8.1 | 0 | ? | ?"), lines[3]  # ordinato per voto
    assert lines[4] == "Alpha | 2-4 | 60 | 2.5 | 7.8 | 3 | 3 | Worker Placement", lines[4]


def test_js_filter():
    sample = ROOT / "data" / "collection.json"
    script = """
const {searchGames} = require('./filter.js');
const data = require('./data/collection.json').games;
const run = (c) => { const r = searchGames(data, c); return {strict: r.strict.map(e=>e.game.name), relaxed: r.relaxed.map(e=>e.game.name), unknown: r.unknownWeight}; };
console.log(JSON.stringify({
  four_hour: run({players:4, maxMinutes:60, weightMin:2.5, weightMax:5, mechanics:'worker placement'}),
  two_players: run({players:2}),
  avoid: run({players:4, exclude:'cooperative'}),
  none: run({players:12}),
}));
"""
    out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    res = json.loads(out)
    # i risultati devono essere ordinati per voto BGG decrescente
    games = {g["name"]: g for g in json.loads(sample.read_text())["games"]}
    for key in ("two_players", "avoid"):
        ratings = [games[n]["avg_rating"] for n in res[key]["strict"]]
        assert ratings == sorted(ratings, reverse=True), (key, ratings)
    assert res["none"]["strict"] == []
    assert all("Pandemic" not in n for n in res["avoid"]["strict"]), "cooperative va escluso"
    for n in res["four_hour"]["strict"]:
        g = games[n]
        assert g["minplayers"] <= 4 <= g["maxplayers"] and g["playingtime"] <= 60 and g["weight"] >= 2.5
        assert any("worker placement" in m.lower() for m in g["mechanics"])
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
