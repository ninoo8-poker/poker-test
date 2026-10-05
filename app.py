"""Poker Ranges Trainer – révision des ranges d'ouverture 100BB.

Lancer en local :  streamlit run app.py
Les ranges sont lues dans data/ranges.json (généré depuis l'Excel, voir convert_excel.py).
"""
import json
import random
from pathlib import Path

import streamlit as st

# ───────────────────────── Configuration ─────────────────────────
st.set_page_config(page_title="Poker Ranges Trainer", page_icon="♠️", layout="centered")

DATA_FILE = Path(__file__).parent / "data" / "ranges.json"
RANKS = "AKQJT98765432"
SUITS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RED_SUITS = {"h", "d"}
COLORS = {"raise": "#e53935", "call": "#00b050", "fold": "#7f7f7f"}
LABELS = {"raise": "Raise", "call": "Call / Limp", "fold": "Fold"}


# ───────────────────────── Données ─────────────────────────
@st.cache_data
def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


DATA = load_data()
POSITIONS = list(DATA.keys())


def grid_hand(i, j):
    """Main affichée en ligne i, colonne j (paires sur la diagonale, suited au-dessus)."""
    if i == j:
        return RANKS[i] * 2
    if i < j:
        return RANKS[i] + RANKS[j] + "s"
    return RANKS[j] + RANKS[i] + "o"


def n_combos(hand):
    return 6 if len(hand) == 2 else (4 if hand[2] == "s" else 12)


def action_text(pos, action):
    if action == "raise":
        return f"Raise {DATA[pos]['raise_size']} BB"
    return LABELS[action]


def random_suits(hand):
    """Tire des couleurs réalistes pour la main (ex. 'AKs' -> A♠ K♠)."""
    r1, r2 = hand[0], hand[1]
    if len(hand) == 3 and hand[2] == "s":
        s = random.choice(list(SUITS))
        return (r1, s), (r2, s)
    s1, s2 = random.sample(list(SUITS), 2)
    return (r1, s1), (r2, s2)


def card_html(rank, suit):
    color = "#d32f2f" if suit in RED_SUITS else "#111"
    r = "10" if rank == "T" else rank
    return (
        f"<span style='display:inline-block;background:#fff;border:2px solid #333;"
        f"border-radius:10px;padding:10px 14px;margin:4px;font-size:2.4rem;"
        f"font-weight:700;color:{color};min-width:70px;text-align:center'>"
        f"{r}{SUITS[suit]}</span>"
    )


def is_boundary(pos, hand, grid_index):
    """Vrai si la main est jouée ou a au moins un voisin (grille) avec une autre action."""
    actions = DATA[pos]["actions"]
    a = actions[hand]
    i, j = grid_index[hand]
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = i + di, j + dj
        if 0 <= ni < 13 and 0 <= nj < 13 and actions[grid_hand(ni, nj)] != a:
            return True
    return False


GRID_INDEX = {grid_hand(i, j): (i, j) for i in range(13) for j in range(13)}


# ───────────────────────── Matrice HTML ─────────────────────────
def matrix_html(pos, highlight=None, cell=44):
    actions = DATA[pos]["actions"]
    rows = []
    for i in range(13):
        tds = []
        for j in range(13):
            h = grid_hand(i, j)
            border = "3px solid #ffd600" if h == highlight else "1px solid #222"
            tds.append(
                f"<td style='background:{COLORS[actions[h]]};color:#fff;border:{border};"
                f"width:{cell}px;height:{cell}px;text-align:center;font-size:.72rem;"
                f"font-weight:600;padding:0'>{h}</td>"
            )
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (
        "<div style='overflow-x:auto'><table style='border-collapse:collapse;margin:auto'>"
        + "".join(rows)
        + "</table></div>"
    )


def legend_html(pos):
    size = DATA[pos]["raise_size"]
    items = [("raise", f"Raise {size} BB"), ("call", "Call / Limp"), ("fold", "Fold")]
    return " &nbsp; ".join(
        f"<span style='display:inline-block;width:14px;height:14px;background:{COLORS[k]};"
        f"border-radius:3px;vertical-align:middle'></span> {t}"
        for k, t in items
    )


def range_stats(pos):
    actions = DATA[pos]["actions"]
    tot = {"raise": 0, "call": 0, "fold": 0}
    for h, a in actions.items():
        tot[a] += n_combos(h)
    return {k: 100 * v / 1326 for k, v in tot.items()}


# ───────────────────────── État de session ─────────────────────────
def init_state():
    s = st.session_state
    s.setdefault("total", 0)
    s.setdefault("good", 0)
    s.setdefault("streak", 0)
    s.setdefault("best", 0)
    s.setdefault("errors", {})  # "POS|hand" -> nb d'erreurs
    s.setdefault("pos_stats", {p: [0, 0] for p in POSITIONS})  # [bonnes, total]
    s.setdefault("q", None)
    s.setdefault("answered", False)
    s.setdefault("last", None)


def reset_stats():
    for k in ("total", "good", "streak", "best"):
        st.session_state[k] = 0
    st.session_state.errors = {}
    st.session_state.pos_stats = {p: [0, 0] for p in POSITIONS}
    st.session_state.q = None
    st.session_state.answered = False
    st.session_state.last = None


def draw_question(positions, mode):
    pool = []
    for p in positions:
        for h in DATA[p]["actions"]:
            pool.append((p, h))

    if mode == "Mains frontières":
        border = [(p, h) for p, h in pool if is_boundary(p, h, GRID_INDEX)]
        pool = border or pool
        weights = [1] * len(pool)
    elif mode == "Focus sur mes erreurs":
        weights = [1 + 6 * st.session_state.errors.get(f"{p}|{h}", 0) for p, h in pool]
    elif mode == "Réaliste (pondéré par combos)":
        weights = [n_combos(h) for _, h in pool]
    else:  # Uniforme
        weights = [1] * len(pool)

    # évite de reposer exactement la même question
    for _ in range(5):
        pos, hand = random.choices(pool, weights=weights, k=1)[0]
        prev = st.session_state.q
        if not prev or (prev["pos"], prev["hand"]) != (pos, hand):
            break
    return {"pos": pos, "hand": hand, "cards": random_suits(hand)}


def answer(choice):
    s = st.session_state
    q = s.q
    correct = DATA[q["pos"]]["actions"][q["hand"]]
    ok = choice == correct
    s.answered = True
    s.last = {"choice": choice, "ok": ok, "correct": correct}
    s.total += 1
    s.pos_stats[q["pos"]][1] += 1
    if ok:
        s.good += 1
        s.pos_stats[q["pos"]][0] += 1
        s.streak += 1
        s.best = max(s.best, s.streak)
    else:
        s.streak = 0
        key = f"{q['pos']}|{q['hand']}"
        s.errors[key] = s.errors.get(key, 0) + 1


def next_question():
    st.session_state.q = draw_question(
        st.session_state.sel_positions or POSITIONS, st.session_state.mode
    )
    st.session_state.answered = False
    st.session_state.last = None


# ───────────────────────── Interface ─────────────────────────
init_state()

st.title("♠️ Poker Ranges Trainer")
st.caption("Ranges d'ouverture 100BB – tous les joueurs avant toi ont fold.")

with st.sidebar:
    st.header("Réglages")
    st.multiselect(
        "Positions à réviser",
        POSITIONS,
        default=POSITIONS,
        key="sel_positions",
    )
    st.radio(
        "Tirage des mains",
        [
            "Uniforme",
            "Réaliste (pondéré par combos)",
            "Mains frontières",
            "Focus sur mes erreurs",
        ],
        key="mode",
        help=(
            "Uniforme : chaque main (169) a la même chance.\n\n"
            "Réaliste : les mains sont tirées comme aux tables (plus de offsuit que de paires).\n\n"
            "Mains frontières : mains à la limite entre deux actions.\n\n"
            "Focus erreurs : revient plus souvent sur les mains ratées."
        ),
    )
    if st.button("Réinitialiser les stats"):
        reset_stats()
        st.rerun()

tab_quiz, tab_ranges, tab_stats = st.tabs(["🎯 Entraînement", "📊 Ranges", "📈 Statistiques"])

# ---------- Entraînement ----------
with tab_quiz:
    s = st.session_state
    acc = f"{100 * s.good / s.total:.0f} %" if s.total else "–"
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{s.good}/{s.total}")
    c2.metric("Précision", acc)
    c3.metric("Série", f"{s.streak}", help=f"Record : {s.best}")

    if s.q is None:
        next_question()
    q = s.q

    st.markdown(f"### Position : **{q['pos']}**")
    st.markdown(
        "<div style='text-align:center'>"
        + card_html(*q["cards"][0])
        + card_html(*q["cards"][1])
        + "</div>",
        unsafe_allow_html=True,
    )

    if not s.answered:
        b1, b2, b3 = st.columns(3)
        b1.button("Fold", use_container_width=True, on_click=answer, args=("fold",))
        b2.button("Raise", use_container_width=True, type="primary", on_click=answer, args=("raise",))
        b3.button("Call / Limp", use_container_width=True, on_click=answer, args=("call",))
    else:
        last = s.last
        if last["ok"]:
            st.success(f"✅ Correct : {action_text(q['pos'], last['correct'])}")
        else:
            st.error(
                f"❌ Raté. Ta réponse : {LABELS[last['choice']]} — "
                f"bonne réponse : **{action_text(q['pos'], last['correct'])}**"
            )
        with st.expander("Voir la range de la position", expanded=not last["ok"]):
            st.markdown(matrix_html(q["pos"], highlight=q["hand"]), unsafe_allow_html=True)
            st.markdown(legend_html(q["pos"]), unsafe_allow_html=True)
        st.button("Question suivante ➜", type="primary", use_container_width=True, on_click=next_question)

# ---------- Ranges ----------
with tab_ranges:
    pos = st.selectbox("Position", POSITIONS, key="view_pos")
    st.markdown(matrix_html(pos), unsafe_allow_html=True)
    st.markdown(
        f"<div style='text-align:center;margin-top:10px'>{legend_html(pos)}</div>",
        unsafe_allow_html=True,
    )
    rs = range_stats(pos)
    st.caption(
        f"Raise : {rs['raise']:.1f} % des combos · Call/Limp : {rs['call']:.1f} % · "
        f"Fold : {rs['fold']:.1f} %"
    )
    st.caption("Paires sur la diagonale · suited (s) au-dessus · offsuit (o) en dessous.")

# ---------- Statistiques ----------
with tab_stats:
    s = st.session_state
    if not s.total:
        st.info("Réponds à quelques questions pour voir tes statistiques.")
    else:
        st.subheader("Précision par position")
        for p in POSITIONS:
            good, tot = s.pos_stats[p]
            if tot:
                st.write(f"**{p}** : {good}/{tot} ({100 * good / tot:.0f} %)")
                st.progress(good / tot)

        st.subheader("Mains les plus ratées")
        if s.errors:
            worst = sorted(s.errors.items(), key=lambda kv: -kv[1])[:15]
            for key, n in worst:
                p, h = key.split("|")
                st.write(
                    f"- **{p} – {h}** : {n} erreur(s) → {action_text(p, DATA[p]['actions'][h])}"
                )
        else:
            st.success("Aucune erreur pour l'instant, bravo !")
