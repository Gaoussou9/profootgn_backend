// src/pages/MatchEventsEditor.jsx
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";

/* -------------------- Utils -------------------- */
const toInt = (v, def = 0) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) && n >= 0 ? n : def;
};
const toast = (msg) => window.alert(msg);

/* -------------------- Autocomplete joueur -------------------- */
function PlayerPicker({ clubId, label, value, onChange, required = false }) {
  // … inchangé …
  // (garde exactement ton code PlayerPicker)
}

/* -------------------- Page -------------------- */
export default function MatchEventsEditor() {
  const { id } = useParams();
  const matchId = toInt(id, null);

  const [m, setMatch] = useState(null);
  const [loading, setLoad] = useState(true);
  const [error, setError] = useState(null);

  // Formulaires (inchangés) …
  const [goalClub, setGoalClub] = useState("home");
  const [goalMinute, setGoalMinute] = useState("");
  const [scorer, setScorer] = useState(null);
  const [assist, setAssist] = useState(null);

  const [cardClub, setCardClub] = useState("home");
  const [cardMinute, setCardMinute] = useState("");
  const [cardPlayer, setCardPlayer] = useState(null);
  const [cardType, setCardType] = useState("Y");

  const homeClubId = m?.home_club;
  const awayClubId = m?.away_club;

  const homeName = m?.home_club_name || "Équipe 1";
  const awayName = m?.away_club_name || "Équipe 2";

  const loadMatch = async () => {
    if (!matchId) return;
    setLoad(true);
    try {
      const r = await api.get(`matches/${matchId}/`);
      setMatch(r.data);
      setError(null);
    } catch (e) {
      setError(e.message || "Erreur de chargement du match");
    } finally {
      setLoad(false);
    }
  };

  useEffect(() => {
    loadMatch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  const clubs = useMemo(
    () => ({
      home: { id: homeClubId, name: homeName },
      away: { id: awayClubId, name: awayName },
    }),
    [homeClubId, awayClubId, homeName, awayName]
  );

  /* ---------- Add Goal / Add Card (inchangés) ---------- */
  // garde ton code onAddGoal, onAddCard, deleteGoal, deleteCard

  if (loading) return <p>Chargement…</p>;
  if (error) return <p className="text-red-600">Erreur : {error}</p>;
  if (!m) return <p>Match introuvable</p>;

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">
          Événements — {homeName} <span className="text-gray-400">vs</span> {awayName}
        </h1>
        <Link to={`/match/${matchId}`} className="text-sm text-blue-600 underline">
          ↩︎ Retour au match
        </Link>
      </div>

      {/* ---- FORM BUTS + CARTONS (inchangés) ---- */}
      {/* ... ton code d’ajout ... */}

      {/* ---- LISTES ---- */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* BUTS */}
        <div className="border rounded-xl p-4 bg-white shadow-sm">
          <h3 className="font-semibold mb-3">Buts</h3>
          {m.goals?.length ? (
            <ul className="space-y-2">
              {m.goals.map((g) => (
                <li
                  key={g.id}
                  className="flex items-center justify-between border rounded px-3 py-2"
                >
                  <div className="text-sm">
                    <span className="font-semibold">{g.minute}'</span>{" "}
                    <span className="text-gray-600">• {g.club_name}</span>{" "}
                    —{" "}
                    <span title={g.player_name}>
                      {g.player_short_name || g.player_name || "?"}
                    </span>
                    {g.assist_name ? (
                      <span
                        className="text-gray-500"
                        title={g.assist_name}
                      >
                        {" "}
                        (passe : {g.assist_short_name || g.assist_name})
                      </span>
                    ) : null}
                  </div>
                  <button
                    className="text-xs text-red-600 hover:underline"
                    onClick={() => deleteGoal(g.id)}
                  >
                    Supprimer
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">Aucun but.</p>
          )}
        </div>

        {/* CARTONS */}
        <div className="border rounded-xl p-4 bg-white shadow-sm">
          <h3 className="font-semibold mb-3">Cartons</h3>
          {m.cards?.length ? (
            <ul className="space-y-2">
              {m.cards.map((c) => (
                <li
                  key={c.id}
                  className="flex items-center justify-between border rounded px-3 py-2"
                >
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-semibold">{c.minute}'</span>{" "}
                    <span className="text-gray-600">• {c.club_name}</span>{" "}
                    — 
                    <img
                      src={c.player_photo || "/player-placeholder.png"}
                      alt={c.player_name || "Joueur"}
                      className="w-6 h-6 rounded-full object-cover inline-block ml-2"
                      onError={(e) =>
                        (e.currentTarget.src = "/player-placeholder.png")
                      }
                    />
                    <span className="ml-2" title={c.player_name}>
                      {c.card_player_short_name || c.player_name || "?"}
                    </span>
                    <span
                      className={`ml-2 text-xs px-1.5 py-0.5 rounded ${
                        c.type === "R"
                          ? "bg-red-100 text-red-700"
                          : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {c.type === "R" ? "Rouge" : "Jaune"}
                    </span>
                  </div>
                  <button
                    className="text-xs text-red-600 hover:underline"
                    onClick={() => deleteCard(c.id)}
                  >
                    Supprimer
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">Aucun carton.</p>
          )}
        </div>
      </div>
    </section>
  );
}
