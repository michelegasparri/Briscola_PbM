"""
Briscola — game engine (v0.1)

Pure game logic. No I/O, no printing, deterministic given its inputs.
The full game state is a plain dict so it serializes cleanly to a token.

Trust model: honor system. The token carries the full state; v0.1 does not
hide information. `player_view` returns the full state but exists as the seam
for adding hidden hands / encryption later without touching game logic.

Card notation
-------------
Suit : one of D (Denari), S (Spade), C (Coppe), B (Bastoni)
Rank : 1..10  (1 = Asso ... 10 = Re)
Card : "<SUIT>-<RANK>"  e.g. "D-1", "S-10", "C-7", "B-9"

IMPORTANT: the numeric rank is NEITHER the point value NOR the trick strength.
Never compare or sort cards by their rank label — use POINTS and STRENGTH.
"""

import base64
import copy
import hashlib
import json
import random
import zlib

VERSION = 3

SUITS = ("D", "S", "C", "B")
RANKS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

# rank -> card points (Asso 11, Tre 10, Re 4, Cavallo 3, Fante 2, rest 0)
POINTS = {1: 11, 2: 0, 3: 10, 4: 0, 5: 0, 6: 0, 7: 0, 8: 2, 9: 3, 10: 4}

# rank -> trick strength, 1 = strongest .. 10 = weakest
# strength order high->low by rank label: 1, 3, 10, 9, 8, 7, 6, 5, 4, 2
STRENGTH = {1: 1, 3: 2, 10: 3, 9: 4, 8: 5, 7: 6, 6: 7, 5: 8, 4: 9, 2: 10}

SUIT_NAMES = {"D": "Denari", "S": "Spade", "C": "Coppe", "B": "Bastoni"}
RANK_NAMES = {
    1: "Asso", 2: "Due", 3: "Tre", 4: "Quattro", 5: "Cinque",
    6: "Sei", 7: "Sette", 8: "Fante", 9: "Cavallo", 10: "Re",
}


class TokenError(Exception):
    """Raised when a token is unreadable, corrupted, or an unsupported version."""


class IllegalMove(Exception):
    """Raised when an attempted move is not allowed."""


# --------------------------------------------------------------------------- #
# Card helpers
# --------------------------------------------------------------------------- #

def make_card(suit, rank):
    return f"{suit}-{rank}"


def card_suit(card):
    return card.split("-", 1)[0]


def card_rank(card):
    return int(card.split("-", 1)[1])


def card_points(card):
    return POINTS[card_rank(card)]


def card_name(card):
    s, r = card_suit(card), card_rank(card)
    return f"{card} ({RANK_NAMES[r]} di {SUIT_NAMES[s]}, {POINTS[r]}pt)"


def full_deck():
    return [make_card(s, r) for s in SUITS for r in RANKS]


def _other(player):
    return 1 - player


# --------------------------------------------------------------------------- #
# Game lifecycle
# --------------------------------------------------------------------------- #

def new_game(seed=None):
    """Create a fresh game state.

    `seed` is initialization entropy only; it is used once to shuffle and is
    NOT stored in the state (storing it would let the opponent reproduce the
    whole deck order). The caller should supply a high-entropy seed.
    """
    rng = random.Random(seed)
    deck = full_deck()
    rng.shuffle(deck)

    hands = [[], []]
    # deal 3 cards each (alternating); order is cosmetic since the deck is shuffled
    for _ in range(3):
        for p in (0, 1):
            hands[p].append(deck.pop(0))

    # The next card sets the trump suit and sits at the bottom of the draw pile
    # (it is the last card drawn). deck[-1] is that exposed card.
    briscola_card = deck[-1]
    briscola_suit = card_suit(briscola_card)

    # A non-secret per-game identifier. Both devices see the same game_id in the
    # token; each device uses it to remember which player it is for this game.
    game_id = format(rng.getrandbits(64), "016x")

    state = {
        "version": VERSION,
        "game_id": game_id,
        "deck": deck,                 # index 0 = next to draw; [-1] = exposed briscola
        "briscola_suit": briscola_suit,
        "briscola_card": briscola_card,
        "hands": hands,
        "table": [],                  # list of [player, card] in play order
        "last_trick": None,           # summary of the previous trick (public)
        "leader": 1,                  # non-starting player (Player 2) leads first
        "turn": 1,
        "captured_points": [0, 0],
        "captured_cards": [0, 0],
        "trick_no": 1,
    }
    return state


def player_view(state, player):
    """Return only what `player` is allowed to see.

    Hidden: the opponent's hand (shown as a count) and the deck's card
    identities (shown as a count). Visible: the viewer's own hand, the table,
    scores, trump, and turn info — all of which are public or belong to the
    viewer.

    The turned-up briscola card is public while it is still the bottom card of
    the draw pile; once drawn it is reported as "set by <card>" (which card
    determined trump is public knowledge either way).

    NOTE: this hides information at the *interface* level only. The token still
    carries the full state (the opponent's device needs it to keep playing), so
    this is display privacy under the honor system — not cryptographic secrecy.
    True secrecy requires encrypting per-player state / mental-poker dealing,
    which is a separate, larger step. Because all display routes through this
    function, that upgrade does not touch game logic.
    """
    opp = _other(player)
    bcard = state["briscola_card"]
    briscola_in_deck = bool(state["deck"]) and state["deck"][-1] == bcard
    return {
        "version": state["version"],
        "game_id": state["game_id"],
        "you": player,
        "briscola_suit": state["briscola_suit"],
        "briscola_card": bcard,
        "briscola_in_deck": briscola_in_deck,
        "your_hand": list(state["hands"][player]),
        "opponent_hand_count": len(state["hands"][opp]),
        "deck_count": len(state["deck"]),
        "table": [list(entry) for entry in state["table"]],
        "last_trick": copy.deepcopy(state.get("last_trick")),
        "captured_points": list(state["captured_points"]),
        "captured_cards": list(state["captured_cards"]),
        "turn": state["turn"],
        "leader": state["leader"],
        "trick_no": state["trick_no"],
    }


def legal_moves(state, player):
    """v0.1: no following-suit rule, so any card in hand is legal."""
    return list(state["hands"][player])


def resolve_trick(table, briscola_suit):
    """Given a completed trick [[leader, c1], [responder, c2]], return winner."""
    (p_lead, c_lead), (p_resp, c_resp) = table[0], table[1]
    s_lead, r_lead = card_suit(c_lead), card_rank(c_lead)
    s_resp, r_resp = card_suit(c_resp), card_rank(c_resp)

    if s_lead == s_resp:
        # same suit (covers both-briscola too): lower STRENGTH value wins
        return p_lead if STRENGTH[r_lead] < STRENGTH[r_resp] else p_resp
    if s_resp == briscola_suit:
        return p_resp
    if s_lead == briscola_suit:
        return p_lead
    # two different non-briscola suits: the leader wins
    return p_lead


def apply_move(state, player, card):
    """Apply a single card play and return the resulting NEW state."""
    if is_terminal(state):
        raise IllegalMove("the game is already over")
    if player != state["turn"]:
        raise IllegalMove(f"not player {player + 1}'s turn")
    if card not in state["hands"][player]:
        raise IllegalMove(f"{card} is not in player {player + 1}'s hand")

    s = copy.deepcopy(state)
    s["hands"][player].remove(card)
    s["table"].append([player, card])

    if len(s["table"]) == 1:
        # first card of the trick: pass to the opponent
        s["turn"] = _other(player)
        return s

    # second card: resolve the trick
    winner = resolve_trick(s["table"], s["briscola_suit"])
    pts = sum(card_points(c) for _, c in s["table"])
    s["last_trick"] = {
        "plays": [list(entry) for entry in s["table"]],   # [[leader, card], [responder, card]]
        "winner": winner,
        "points": pts,
    }
    s["captured_points"][winner] += pts
    s["captured_cards"][winner] += 2
    s["table"] = []
    s["trick_no"] += 1

    # draws: winner draws first, then loser (this can flip who leads next)
    for p in (winner, _other(winner)):
        if s["deck"]:
            s["hands"][p].append(s["deck"].pop(0))

    s["leader"] = winner
    s["turn"] = winner
    return s


def is_terminal(state):
    """Game over when all 40 cards have been captured."""
    return sum(state["captured_cards"]) == 40


def result(state):
    """Return {'winner': 0|1|None, 'points': [p0, p1]}. None winner = draw."""
    p0, p1 = state["captured_points"]
    if p0 > p1:
        winner = 0
    elif p1 > p0:
        winner = 1
    else:
        winner = None
    return {"winner": winner, "points": [p0, p1]}


# --------------------------------------------------------------------------- #
# Serialization  (state <-> token)
#   state dict -> JSON -> zlib -> urlsafe base64
#   wrapper carries a short checksum for corruption detection (not security)
# --------------------------------------------------------------------------- #

def _canonical(core):
    return json.dumps(core, sort_keys=True, separators=(",", ":"))


def serialize(state):
    core = {k: v for k, v in state.items() if k != "checksum"}
    checksum = hashlib.sha256(_canonical(core).encode()).hexdigest()[:8]
    wrapper = {"data": core, "sum": checksum}
    raw = json.dumps(wrapper, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode()


def deserialize(token):
    try:
        comp = base64.urlsafe_b64decode(token.strip().encode())
        raw = zlib.decompress(comp)
        wrapper = json.loads(raw)
        core = wrapper["data"]
        claimed = wrapper["sum"]
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad token
        raise TokenError("token is unreadable or garbled") from exc

    if hashlib.sha256(_canonical(core).encode()).hexdigest()[:8] != claimed:
        raise TokenError("token failed its checksum (corrupted in transit)")
    if core.get("version") != VERSION:
        raise TokenError(
            f"unsupported token version {core.get('version')} (this build is v{VERSION})"
        )
    return core
