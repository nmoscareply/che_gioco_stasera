// Logica di filtro pura, senza DOM: usata dalla pagina e testabile con Node.

function terms(text) {
  return (text || "").split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
}

function tagsOf(g) {
  return [...(g.mechanics || []), ...(g.categories || [])].map((t) => t.toLowerCase());
}

function hasAll(g, list) {
  const tags = tagsOf(g);
  return list.every((t) => tags.some((x) => x.includes(t)));
}

function hasAny(g, list) {
  const tags = tagsOf(g);
  return list.some((t) => tags.some((x) => x.includes(t)));
}

// criteria: { players, maxMinutes, weightMin, weightMax, mechanics (string), exclude (string) }
function searchGames(games, c) {
  const must = terms(c.mechanics);
  const avoid = terms(c.exclude);
  const strict = [];
  const relaxed = [];
  let unknownWeight = 0;

  for (const g of games) {
    const notes = [];

    if (c.players && g.minplayers && g.maxplayers && !(g.minplayers <= c.players && c.players <= g.maxplayers)) continue;
    if (must.length && !hasAll(g, must)) continue;
    if (avoid.length && hasAny(g, avoid)) continue;

    if (c.maxMinutes && g.playingtime) {
      if (g.playingtime > c.maxMinutes * 1.25) continue;
      if (g.playingtime > c.maxMinutes) notes.push(`dura ${g.playingtime} min, un po' oltre il limite`);
    }

    if (c.weightMin != null || c.weightMax != null) {
      if (g.weight == null) {
        unknownWeight++;
        continue;
      }
      if (c.weightMax != null) {
        if (g.weight > c.weightMax + 0.5) continue;
        if (g.weight > c.weightMax) notes.push(`peso ${g.weight.toFixed(1)}, un po' sopra il massimo`);
      }
      if (c.weightMin != null) {
        if (g.weight < c.weightMin - 0.5) continue;
        if (g.weight < c.weightMin) notes.push(`peso ${g.weight.toFixed(1)}, un po' sotto il minimo`);
      }
    }

    (notes.length ? relaxed : strict).push({ game: g, notes });
  }

  const byRating = (a, b) =>
    (b.game.avg_rating || 0) - (a.game.avg_rating || 0) || (a.game.numplays || 0) - (b.game.numplays || 0);
  strict.sort(byRating);
  relaxed.sort(byRating);
  return { strict, relaxed, unknownWeight };
}

if (typeof module !== "undefined") module.exports = { searchGames, terms };
