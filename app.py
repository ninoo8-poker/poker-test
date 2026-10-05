"""Poker Ranges Trainer – révision des ranges d'ouverture 100BB.

Lancer en local :  streamlit run app.py
Les ranges sont embarquées dans ce fichier (RAW_RANGES) : aucun autre fichier requis.
"""
import os
import re
import random
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

import streamlit as st


def _stretch_kwargs(fn):
    """Compat Streamlit : `width="stretch"` (récent) ou `use_container_width=True` (ancien)."""
    import inspect

    try:
        if "width" in inspect.signature(fn).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


FULL_BTN = _stretch_kwargs(st.button)
FULL_DF = _stretch_kwargs(st.dataframe)


# ───────────────────────── Configuration ─────────────────────────
st.set_page_config(page_title="Poker Ranges Trainer", page_icon="♠️", layout="centered")

RANKS = "AKQJT98765432"
SUITS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RED_SUITS = {"h", "d"}
COLORS = {"raise": "#e53935", "call": "#00b050", "fold": "#7f7f7f"}
LABELS = {"raise": "Raise", "call": "Call / Limp", "fold": "Fold"}


# ───────────── Ranges embarquées (générées depuis range_KT_100BB.xlsx) ─────────────
# Pour chaque position : (taille du raise en BB, 13 lignes de 13 caractères).
# Ordre = grille de l'Excel (paires en diagonale, suited au-dessus, offsuit en dessous).
# r = raise · c = call/limp · f = fold
RAW_RANGES = {
    "UTG": ("2,1", [
        "rrrrrrrrrrrrf",
        "rrrrrrrffffff",
        "rrrrrrfffffff",
        "rffrrrfffffff",
        "ffffrrrffffff",
        "fffffrfffffff",
        "ffffffrffffff",
        "fffffffrfffff",
        "ffffffffrrfff",
        "fffffffffrfff",
        "ffffffffffrff",
        "fffffffffffff",
        "fffffffffffff",
    ]),
    "UTG1": ("2,1", [
        "rrrrrrrrrrrrr",
        "rrrrrrrrfrfff",
        "rrrrrrfffffff",
        "rrfrrrfffffff",
        "rfffrrrffffff",
        "fffffrrffffff",
        "ffffffrffffff",
        "fffffffrfffff",
        "ffffffffrrfff",
        "fffffffffrfff",
        "ffffffffffrff",
        "fffffffffffrf",
        "fffffffffffff",
    ]),
    "LJ": ("2,1", [
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrfff",
        "rrrrrrrffffff",
        "rrrrrrrffffff",
        "rrfrrrrffffff",
        "fffffrrrfffff",
        "ffffffrrfffff",
        "fffffffrrffff",
        "ffffffffrrfff",
        "fffffffffrrff",
        "ffffffffffrff",
        "fffffffffffrf",
        "ffffffffffffr",
    ]),
    "HJ": ("2,1", [
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrf",
        "rrrrrrrrrffff",
        "rrrrrrrffffff",
        "rrrrrrrrfffff",
        "rffffrrrfffff",
        "ffffffrrrffff",
        "fffffffrrffff",
        "ffffffffrrfff",
        "fffffffffrrff",
        "ffffffffffrff",
        "fffffffffffrf",
        "ffffffffffffr",
    ]),
    "CO": ("2,2", [
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrf",
        "rrrrrrrrrrfff",
        "rrrrrrrrrffff",
        "rrrfrrrrrffff",
        "rfffffrrrrfff",
        "rffffffrrrfff",
        "ffffffffrrrff",
        "rffffffffrrff",
        "ffffffffffrff",
        "fffffffffffrf",
        "ffffffffffffr",
    ]),
    "BTN": ("2,5", [
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrr",
        "rrrrrrrrrrrrf",
        "rrrrrrrrrrfff",
        "rrrrrrrrrrfff",
        "rrffffrrrrrff",
        "rrffffffrrrff",
        "rrfffffffrrrf",
        "rfffffffffrrf",
        "rffffffffffrf",
        "rfffffffffffr",
    ]),
    "SB": ("3,5", [
        "crcrrcrccrccc",
        "ccrrrcccccccc",
        "cccrccccccccc",
        "ccccrcccccccc",
        "ccccccccccrcc",
        "ccccccccccccc",
        "ccccccccccccc",
        "ccccccccccccc",
        "ccccccccccccc",
        "ccccccccccrcc",
        "ccccccccccccc",
        "cccccffffcccc",
        "cccccfffffffc",
    ]),
}

RANKS_STR = "AKQJT98765432"
ACTION_OF = {"r": "raise", "c": "call", "f": "fold"}


def _hand_name(i, j):
    if i == j:
        return RANKS_STR[i] * 2
    return RANKS_STR[i] + RANKS_STR[j] + "s" if i < j else RANKS_STR[j] + RANKS_STR[i] + "o"


DATA = {
    pos: {
        "raise_size": size,
        "actions": {
            _hand_name(i, j): ACTION_OF[rows[i][j]] for i in range(13) for j in range(13)
        },
    }
    for pos, (size, rows) in RAW_RANGES.items()
}
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


# Ordre des places dans le sens horaire (le bouton du dealer est sur BTN)
TABLE_SEATS = ["BTN", "SB", "BB", "UTG", "UTG1", "LJ", "HJ", "CO"]


def table_svg(highlight=None):
    """Schéma d'une table 8-max : places nommées, bouton du dealer, position active en surbrillance."""
    import math

    cx, cy = 170, 140
    parts = [
        "<svg viewBox='0 0 340 280' xmlns='http://www.w3.org/2000/svg' "
        "style='width:100%;max-width:340px;height:auto'>",
        f"<ellipse cx='{cx}' cy='{cy}' rx='108' ry='72' fill='#0b6b3a' stroke='#5d3a1a' stroke-width='9'/>",
        f"<text x='{cx}' y='{cy + 5}' text-anchor='middle' font-size='13' fill='#ffffff' "
        "opacity='0.35' font-family='sans-serif' font-weight='700'>8-MAX</text>",
    ]
    for k, seat in enumerate(TABLE_SEATS):
        ang = math.radians(90 + 45 * k)  # BTN en bas, sens horaire à l'écran
        x = cx + 135 * math.cos(ang)
        y = cy + 100 * math.sin(ang)
        active = seat == highlight
        playable = seat in DATA
        fill = "#ffd600" if active else ("#37474f" if playable else "#78909c")
        txt = "#111" if active else "#fff"
        stroke = "#ffffff" if active else "#222"
        r = 25 if active else 22
        parts.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{r}' fill='{fill}' stroke='{stroke}' stroke-width='2.5'/>"
            f"<text x='{x:.1f}' y='{y + 4:.1f}' text-anchor='middle' font-size='12' font-weight='700' "
            f"font-family='sans-serif' fill='{txt}'>{seat}</text>"
        )
        if seat == "BTN":  # jeton dealer placé vers le centre de la table
            bx = cx + 78 * math.cos(ang) * 0.9
            by = cy + 52 * math.sin(ang) * 0.9
            parts.append(
                f"<circle cx='{bx:.1f}' cy='{by:.1f}' r='11' fill='#ffffff' stroke='#222' stroke-width='2'/>"
                f"<text x='{bx:.1f}' y='{by + 4:.1f}' text-anchor='middle' font-size='12' font-weight='800' "
                "font-family='sans-serif' fill='#c62828'>D</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def table_block(highlight=None):
    """Schéma + petite légende, prêt à passer à st.markdown(unsafe_allow_html=True)."""
    return (
        "<div style='text-align:center'>"
        + table_svg(highlight)
        + "<div style='font-size:.8rem;opacity:.75;margin-top:4px'>"
        "Sens horaire : BTN → SB → BB → UTG → UTG1 → LJ → HJ → CO<br>"
        "<b>D</b> = bouton du dealer</div></div>"
    )


def range_stats(pos):
    actions = DATA[pos]["actions"]
    tot = {"raise": 0, "call": 0, "fold": 0}
    for h, a in actions.items():
        tot[a] += n_combos(h)
    return {k: 100 * v / 1326 for k, v in tot.items()}


# ───────────────────────── Classement : stockage ─────────────────────────
# Par défaut : base SQLite locale (partagée entre tous les joueurs tant que l'app tourne,
# mais effacée quand Streamlit Cloud redémarre l'app).
# Pour un classement permanent : renseigner [supabase] url / key dans les secrets Streamlit
# (voir README).
DB_PATH = os.environ.get("SCORES_DB", os.path.join(tempfile.gettempdir(), "poker_trainer_scores.db"))
QUIZ_LENGTHS = [10, 20, 50]
MAX_SECONDS_PER_QUESTION = 30  # plafonne le temps compté par question
PSEUDO_RE = re.compile(r"^[\w][\w .\-]{1,19}$")  # 2 à 20 caractères


def _supabase_cfg():
    try:
        cfg = st.secrets["supabase"]
        return str(cfg["url"]).rstrip("/"), str(cfg["key"])
    except Exception:
        return None


def storage_is_persistent():
    return _supabase_cfg() is not None


def _db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute(
        "CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY AUTOINCREMENT, pseudo TEXT, "
        "score INTEGER, n INTEGER, seconds REAL, created_at TEXT)"
    )
    return con


def save_score(pseudo, score, n, seconds):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cfg = _supabase_cfg()
    if cfg:
        try:
            import requests

            url, key = cfg
            r = requests.post(
                f"{url}/rest/v1/scores",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"pseudo": pseudo, "score": score, "n": n, "seconds": seconds},
                timeout=8,
            )
            r.raise_for_status()
            return
        except Exception:
            st.session_state["storage_warning"] = (
                "Supabase injoignable : score enregistré en local (temporaire)."
            )
    with _db() as con:
        con.execute(
            "INSERT INTO scores (pseudo, score, n, seconds, created_at) VALUES (?,?,?,?,?)",
            (pseudo, score, n, seconds, now),
        )


def fetch_scores(n):
    """Meilleur résultat de chaque pseudo pour un quiz de n questions, trié du meilleur au moins bon."""
    rows = None
    cfg = _supabase_cfg()
    if cfg:
        try:
            import requests

            url, key = cfg
            r = requests.get(
                f"{url}/rest/v1/scores",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                params={
                    "n": f"eq.{n}",
                    "select": "pseudo,score,n,seconds,created_at",
                    "order": "score.desc,seconds.asc",
                    "limit": "500",
                },
                timeout=8,
            )
            r.raise_for_status()
            rows = r.json()
        except Exception:
            st.session_state["storage_warning"] = "Supabase injoignable : classement local affiché."
    if rows is None:
        with _db() as con:
            cur = con.execute(
                "SELECT pseudo, score, n, seconds, created_at FROM scores WHERE n=? "
                "ORDER BY score DESC, seconds ASC LIMIT 500",
                (n,),
            )
            rows = [dict(zip(("pseudo", "score", "n", "seconds", "created_at"), r)) for r in cur]
    best, seen = [], set()
    for r in sorted(rows, key=lambda r: (-r["score"], r["seconds"])):
        k = r["pseudo"].strip().lower()
        if k not in seen:
            seen.add(k)
            best.append(r)
    return best


def leaderboard_rows(n, me=None, limit=20):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    out = []
    for rank, r in enumerate(fetch_scores(n)[:limit], start=1):
        name = r["pseudo"] + ("  ← toi" if me and r["pseudo"].strip().lower() == me.lower() else "")
        out.append(
            {
                "Rang": medals.get(rank, str(rank)),
                "Pseudo": name,
                "Score": f"{r['score']}/{r['n']}",
                "Précision": f"{100 * r['score'] / r['n']:.0f} %",
                "Temps": f"{r['seconds']:.1f} s",
                "Date": str(r["created_at"])[:10],
            }
        )
    return out


def my_rank(n, pseudo):
    for rank, r in enumerate(fetch_scores(n), start=1):
        if r["pseudo"].strip().lower() == pseudo.lower():
            return rank
    return None


# ───────────────────────── Mode Quiz : logique ─────────────────────────
def start_quiz(pseudo, n):
    """Renvoie un message d'erreur, ou None si le quiz démarre."""
    pseudo = (pseudo or "").strip()
    if not PSEUDO_RE.match(pseudo):
        return "Pseudo invalide : 2 à 20 caractères (lettres, chiffres, espace, . - _)."
    st.session_state.pseudo_ok = pseudo
    st.session_state.qz = {
        "pseudo": pseudo, "n": n, "i": 0, "score": 0, "seconds": 0.0,
        "q": None, "answered": False, "last": None, "done": False, "wrong": [], "rank": None,
    }
    _quiz_draw()
    return None


def _quiz_draw():
    qz = st.session_state.qz
    qz["q"] = draw_question(POSITIONS, "Uniforme", prev=qz["q"])
    qz["q"]["t0"] = time.time()
    qz["answered"] = False
    qz["last"] = None


def quiz_answer(choice):
    qz = st.session_state.qz
    q = qz["q"]
    correct = DATA[q["pos"]]["actions"][q["hand"]]
    qz["seconds"] += min(time.time() - q["t0"], MAX_SECONDS_PER_QUESTION)
    ok = choice == correct
    qz["answered"] = True
    qz["last"] = {"ok": ok, "choice": choice, "correct": correct}
    if ok:
        qz["score"] += 1
    else:
        qz["wrong"].append({"pos": q["pos"], "hand": q["hand"], "choice": choice, "correct": correct})


def quiz_next():
    qz = st.session_state.qz
    qz["i"] += 1
    _quiz_draw()


def quiz_finish():
    qz = st.session_state.qz
    qz["i"] += 1
    qz["done"] = True
    save_score(qz["pseudo"], qz["score"], qz["n"], round(qz["seconds"], 1))
    qz["rank"] = my_rank(qz["n"], qz["pseudo"])


def quiz_reset():
    st.session_state.qz = None


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
    s.setdefault("qz", None)


def reset_stats():
    for k in ("total", "good", "streak", "best"):
        st.session_state[k] = 0
    st.session_state.errors = {}
    st.session_state.pos_stats = {p: [0, 0] for p in POSITIONS}
    st.session_state.q = None
    st.session_state.answered = False
    st.session_state.last = None


def draw_question(positions, mode, prev=None):
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
        last_q = prev if prev is not None else st.session_state.get("q")
        if not last_q or (last_q["pos"], last_q["hand"]) != (pos, hand):
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
    st.caption("S'appliquent à l'onglet Entraînement. Le mode Quiz a des règles fixes.")
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

tab_quiz, tab_challenge, tab_ranges, tab_stats = st.tabs(
    ["🎯 Entraînement", "🏆 Quiz & classement", "📊 Ranges", "📈 Statistiques"]
)

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

    col_main, col_table = st.columns([3, 2])
    with col_table:
        st.markdown(table_block(q["pos"]), unsafe_allow_html=True)
    with col_main:
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
            b1.button("Fold", **FULL_BTN, on_click=answer, args=("fold",))
            b2.button("Raise", **FULL_BTN, type="primary", on_click=answer, args=("raise",))
            b3.button("Call / Limp", **FULL_BTN, on_click=answer, args=("call",))
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
            st.button("Question suivante ➜", type="primary", **FULL_BTN, on_click=next_question)

# ---------- Quiz & classement ----------
with tab_challenge:
    qz = st.session_state.qz
    running = bool(qz and not qz["done"])

    st.subheader("🏆 Mode Quiz")
    st.caption(
        "Mêmes règles pour tous : toutes les positions, tirage uniforme, aucune aide. "
        "Classement : meilleur score, puis temps de réponse total le plus court."
    )
    n_view = st.selectbox("Nombre de questions", QUIZ_LENGTHS, index=1, key="quiz_n", disabled=running)

    # --- Écran de démarrage ---
    if qz is None:
        st.text_input("Ton pseudo (visible par tous dans le classement)", key="pseudo", max_chars=20)
        if st.button("Commencer le quiz", type="primary", **FULL_BTN):
            err = start_quiz(st.session_state.get("pseudo", ""), n_view)
            if err:
                st.error(err)
            else:
                st.rerun()

    # --- Quiz en cours ---
    elif not qz["done"]:
        q = qz["q"]
        st.progress(qz["i"] / qz["n"], text=f"Question {qz['i'] + 1} / {qz['n']} · score {qz['score']}")
        col_main, col_table = st.columns([3, 2])
        with col_table:
            st.markdown(table_block(q["pos"]), unsafe_allow_html=True)
        with col_main:
            st.markdown(f"### Position : **{q['pos']}**")
            st.markdown(
                "<div style='text-align:center'>"
                + card_html(*q["cards"][0])
                + card_html(*q["cards"][1])
                + "</div>",
                unsafe_allow_html=True,
            )
            if not qz["answered"]:
                b1, b2, b3 = st.columns(3)
                b1.button("Fold", **FULL_BTN, key="qz_f", on_click=quiz_answer, args=("fold",))
                b2.button("Raise", **FULL_BTN, key="qz_r", type="primary", on_click=quiz_answer, args=("raise",))
                b3.button("Call / Limp", **FULL_BTN, key="qz_c", on_click=quiz_answer, args=("call",))
            else:
                last = qz["last"]
                if last["ok"]:
                    st.success("✅ Correct")
                else:
                    st.error(f"❌ Raté — bonne réponse : **{action_text(q['pos'], last['correct'])}**")
                is_last = qz["i"] + 1 >= qz["n"]
                st.button(
                    "Voir mon résultat 🏁" if is_last else "Question suivante ➜",
                    type="primary", **FULL_BTN, key="qz_next",
                    on_click=quiz_finish if is_last else quiz_next,
                )
        st.button("Abandonner", key="qz_abort", on_click=quiz_reset)

    # --- Résultat ---
    else:
        pct = 100 * qz["score"] / qz["n"]
        r1, r2, r3 = st.columns(3)
        r1.metric("Score", f"{qz['score']}/{qz['n']}")
        r2.metric("Précision", f"{pct:.0f} %")
        r3.metric("Temps", f"{qz['seconds']:.1f} s")
        if qz["rank"]:
            st.success(f"**{qz['pseudo']}**, tu es n°{qz['rank']} du classement ({qz['n']} questions) !")
        if qz["wrong"]:
            with st.expander(f"Mes erreurs ({len(qz['wrong'])})", expanded=True):
                for w in qz["wrong"]:
                    st.write(
                        f"- **{w['pos']} – {w['hand']}** : tu as répondu {LABELS[w['choice']]}, "
                        f"il fallait {action_text(w['pos'], w['correct'])}"
                    )
        else:
            st.balloons()
            st.success("Sans-faute ! 🎉")
        st.button("Rejouer", type="primary", **FULL_BTN, key="qz_again", on_click=quiz_reset)

    # --- Classement ---
    st.divider()
    st.subheader(f"Classement · {n_view} questions")
    me = (qz or {}).get("pseudo") or (st.session_state.get("pseudo") or "").strip() or None
    rows = leaderboard_rows(n_view, me=me)
    if rows:
        st.dataframe(rows, hide_index=True, **FULL_DF)
    else:
        st.info("Aucun score pour l'instant : sois le premier !")
    if st.session_state.get("storage_warning"):
        st.warning(st.session_state["storage_warning"])
    if not storage_is_persistent():
        st.caption(
            "ℹ️ Classement temporaire : il est partagé entre tous les joueurs mais se réinitialise "
            "quand l'app redémarre. Voir le README pour le rendre permanent."
        )

# ---------- Ranges ----------
with tab_ranges:
    pos = st.selectbox("Position", POSITIONS, key="view_pos")
    st.markdown(table_block(pos), unsafe_allow_html=True)
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
