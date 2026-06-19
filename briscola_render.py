"""
Briscola - rendering (v0.4.0)

Pure presentation: turns a `player_view` dict into ASCII-art text. No I/O, no
game logic, no access to the full state - it only ever receives the redacted
view, so it cannot render the opponent's hidden cards.

Cards are drawn as boxes with 5 interior rows. Suits use simple ASCII glyphs
for the four Italian suits:

    (o) Denari      \\_/ Coppe      -+> Spade      o== Bastoni
"""

import briscola_engine as be

CARD_W = 7          # total card width (border + 5 interior + border)
CARD_SEP = "  "     # gap between adjacent cards in a row

SUIT_GLYPH = {
    "D": "(o)",     # Denari  - a coin
    "C": "\\_/",    # Coppe   - a cup
    "S": "-+>",     # Spade   - a sword
    "B": "o==",     # Bastoni - a baton
}

LEGEND = "suits:  (o)=Denari   \\_/=Coppe   -+>=Spade   o===Bastoni"


# --------------------------------------------------------------------------- #
# Card primitives - each returns a list of CARD_W-wide lines (7 lines tall)
# --------------------------------------------------------------------------- #

def card_face(card):
    rank = card.split("-", 1)[1]            # "1".."10"
    glyph = SUIT_GLYPH[be.card_suit(card)]
    edge = "+-----+"
    return [
        edge,
        f"|{rank.ljust(5)}|",               # rank, top-left
        "|     |",
        f"|{glyph.center(5)}|",             # suit glyph, centered
        "|     |",
        f"|{rank.rjust(5)}|",               # rank, bottom-right
        edge,
    ]


def card_back():
    edge = "+-----+"
    a, b = "|x x x|", "| x x |"
    return [edge, a, b, a, b, a, edge]


# --------------------------------------------------------------------------- #
# Layout helpers
# --------------------------------------------------------------------------- #

def hcat(blocks, sep=CARD_SEP):
    """Concatenate blocks (each a list of lines) side by side."""
    blocks = [b for b in blocks if b]
    if not blocks:
        return []
    widths = [max(len(line) for line in b) for b in blocks]
    height = max(len(b) for b in blocks)
    out = []
    for r in range(height):
        row = []
        for b, w in zip(blocks, widths):
            row.append((b[r] if r < len(b) else "").ljust(w))
        out.append(sep.join(row))
    return out


def labeled(label, block):
    return [label] + block


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def _card_phrase(card):
    rank = card.split("-", 1)[1]
    return f"{rank} di {be.SUIT_NAMES[be.card_suit(card)]}"


def last_trick_line(view):
    lt = view.get("last_trick")
    if not lt:
        return "Last trick: -  (game start)"
    a, b = lt["plays"][0], lt["plays"][1]
    return (
        f"Last trick - P{a[0] + 1}: {_card_phrase(a[1])}, "
        f"P{b[0] + 1}: {_card_phrase(b[1])} "
        f"-> P{lt['winner'] + 1} wins (+{lt['points']})"
    )


def status_line(view):
    cp = view["captured_points"]
    return (
        f"Trick {view['trick_no']}  |  Deck {view['deck_count']}  |  "
        f"Score P1 {cp[0]} - P2 {cp[1]}  |  Trump: {be.SUIT_NAMES[view['briscola_suit']]}"
    )


def trump_block(view):
    label = f"TRUMP ({be.SUIT_NAMES[view['briscola_suit']]})"
    if not view["briscola_in_deck"]:
        label += " [drawn]"
    return labeled(label, card_face(view["briscola_card"]))


def opponent_block(view):
    n = view["opponent_hand_count"]
    if n == 0:
        return [f"OPPONENT ({n})", "(no cards)"]
    return labeled(f"OPPONENT ({n})", hcat([card_back() for _ in range(n)]))


def table_block(view):
    plays = view["table"]
    if not plays:
        return ["ON THE TABLE:", "(empty - you lead this trick)"]
    cards = []
    for p, c in plays:
        who = "You" if p == view["you"] else f"Player {p + 1}"
        cards.append(labeled(f"{who}:", card_face(c)))
    return ["ON THE TABLE:"] + hcat(cards, sep="    ")


def hand_block(view):
    cards = view["your_hand"]
    if not cards:
        return ["YOUR HAND:", "(no cards)"]
    row = hcat([card_face(c) for c in cards])
    idx = CARD_SEP.join(f"[{i}]".center(CARD_W) for i in range(len(cards)))
    return ["YOUR HAND:"] + row + [idx]


# --------------------------------------------------------------------------- #
# Whole board
# --------------------------------------------------------------------------- #

def render_board(view):
    lines = []
    lines.append(last_trick_line(view))
    lines.append(status_line(view))
    lines.append("")
    lines += hcat([trump_block(view), opponent_block(view)], sep="       ")
    lines.append("")
    lines += table_block(view)
    lines.append("")
    lines += hand_block(view)
    lines.append("")
    lines.append(LEGEND)
    return "\n".join(lines)
