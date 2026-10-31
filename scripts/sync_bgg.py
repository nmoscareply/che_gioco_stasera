"""Scarica la collezione BGG e i dettagli dei giochi, e scrive data/collection.json.

Uso locale:  BGG_USERNAME=nkbobo BGG_TOKEN=... python scripts/sync_bgg.py
Nella GitHub Action le variabili arrivano da variabili e Secrets del repository.
"""

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import httpx

USERNAME = os.getenv("BGG_USERNAME", "nkbobo")
TOKEN = os.getenv("BGG_TOKEN", "")
BASE = "https://boardgamegeek.com/xmlapi2"
OUT = Path(__file__).resolve().parent.parent / "data" / "collection.json"
TXT = OUT.with_name("collection.txt")


def _int(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _float(v, default=None):
    try:
        f = float(v)
        return f if f > 0 else default
    except (TypeError, ValueError):
        return default


def parse_collection(root):
    games = []
    for item in root.findall("item"):
        status = item.find("status")
        if status is not None and status.get("own") != "1":
            continue
        stats = item.find("stats")
        s = stats.attrib if stats is not None else {}
        rating = stats.find("rating") if stats is not None else None
        avg = rating.find("average") if rating is not None else None
        name = item.find("name")
        year = item.find("yearpublished")
        plays = item.find("numplays")
        gid = _int(item.get("objectid"))
        if not gid:
            continue
        games.append(
            {
                "id": gid,
                "name": name.text if name is not None else "?",
                "year": _int(year.text) if year is not None else None,
                "minplayers": _int(s.get("minplayers")),
                "maxplayers": _int(s.get("maxplayers")),
                "playingtime": _int(s.get("playingtime")) or _int(s.get("maxplaytime")),
                "numplays": _int(plays.text, 0) if plays is not None else 0,
                "avg_rating": _float(avg.get("value")) if avg is not None else None,
            }
        )
    return games


def parse_things(root):
    out = {}
    for item in root.findall("item"):
        gid = _int(item.get("id"))
        if not gid:
            continue
        w = item.find("statistics/ratings/averageweight")
        best = []
        poll = next((p for p in item.findall("poll") if p.get("name") == "suggested_numplayers"), None)
        if poll is not None:
            for res in poll.findall("results"):
                n = res.get("numplayers", "")
                if not n.isdigit():
                    continue
                votes = {r.get("value"): _int(r.get("numvotes"), 0) for r in res.findall("result")}
                b, rec, nr = votes.get("Best", 0), votes.get("Recommended", 0), votes.get("Not Recommended", 0)
                if b + rec + nr and b >= rec and b >= nr:
                    best.append(int(n))
        thumb = item.find("thumbnail")
        out[gid] = {
            "weight": _float(w.get("value")) if w is not None else None,
            "mechanics": [l.get("value") for l in item.findall("link") if l.get("type") == "boardgamemechanic"],
            "categories": [l.get("value") for l in item.findall("link") if l.get("type") == "boardgamecategory"],
            "best": best,
            "thumbnail": thumb.text.strip() if thumb is not None and thumb.text else None,
        }
    return out


def fetch_xml(client, url, params=None):
    for _ in range(15):
        r = client.get(url, params=params)
        if r.status_code in (202, 429):
            time.sleep(5 if r.status_code == 202 else 15)
            continue
        r.raise_for_status()
        root = ET.fromstring(r.content)
        if root.tag == "message":  # richiesta in coda
            time.sleep(5)
            continue
        return root
    raise RuntimeError(f"BGG non ha risposto in tempo: {url}")


def compact_text(games, updated):
    """Una riga per gioco, pensata per essere letta da un agente LLM con pochi token."""
    lines = [
        f"COLLEZIONE BGG di {USERNAME}, aggiornata {updated}. {len(games)} giochi (espansioni escluse).",
        "Colonne: nome | giocatori | durata in minuti | peso 1-5 | voto medio utenti BGG | partite giocate | ottimale a (giocatori) | meccaniche",
        "Il simbolo ? indica un dato non disponibile.",
    ]
    for g in sorted(games, key=lambda x: -(x["avg_rating"] or 0)):
        lo, hi = g["minplayers"], g["maxplayers"]
        players = "?" if not lo else (str(lo) if lo == hi else f"{lo}-{hi}")
        weight = f"{g['weight']:.1f}" if g.get("weight") else "?"
        rating = f"{g['avg_rating']:.1f}" if g.get("avg_rating") else "?"
        best = ",".join(map(str, g.get("best") or [])) or "?"
        mech = ", ".join((g.get("mechanics") or [])[:5]) or "?"
        lines.append(
            f"{g['name']} | {players} | {g.get('playingtime') or '?'} | {weight} | {rating} | {g.get('numplays', 0)} | {best} | {mech}"
        )
    return "\n".join(lines) + "\n"


def main():
    if not TOKEN:
        print("Manca BGG_TOKEN", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "bgg-picker/1.0"}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        root = fetch_xml(
            client,
            f"{BASE}/collection",
            {"username": USERNAME, "own": 1, "stats": 1, "subtype": "boardgame", "excludesubtype": "boardgameexpansion"},
        )
        games = parse_collection(root)
        print(f"Collezione: {len(games)} giochi")
        if not games:
            print("Collezione vuota: non sovrascrivo i dati esistenti", file=sys.stderr)
            sys.exit(1)
        ids = [g["id"] for g in games]
        details = {}
        for i in range(0, len(ids), 20):
            batch = ids[i : i + 20]
            details.update(parse_things(fetch_xml(client, f"{BASE}/thing", {"id": ",".join(map(str, batch)), "stats": 1})))
            print(f"Dettagli: {min(i + 20, len(ids))}/{len(ids)}")
            time.sleep(2)

    for g in games:
        d = details.get(g["id"], {})
        g["weight"] = d.get("weight")
        g["mechanics"] = d.get("mechanics", [])
        g["categories"] = d.get("categories", [])
        g["best"] = d.get("best", [])
        g["thumbnail"] = d.get("thumbnail")
    games.sort(key=lambda g: g["name"].lower())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    updated = datetime.now(timezone.utc).isoformat(timespec="minutes")
    payload = {"updated": updated, "user": USERNAME, "games": games}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    TXT.write_text(compact_text(games, updated), encoding="utf-8")
    print(f"Scritto {OUT} e {TXT}")


if __name__ == "__main__":
    main()
