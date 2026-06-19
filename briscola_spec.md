# Briscola (String-Passing) — Specification v0.4.0

*Current spec. Supersedes v0.3 / v0.1. Reflects what is implemented.*

## 1. Purpose & Concept

A two-player, serverless implementation of **Briscola**. No server and no live
connection: the **complete game state is serialized into a single token
string** that players exchange manually. The token *is* the source of truth and
the save file. Turns are asynchronous — load the latest token, move, emit a new
token to send to the opponent.

## 2. Trust Model

**Honor system with interface-level hiding.** The opponent's hand and the deck's
upcoming cards are redacted from everything displayed (via `player_view`); a
player sees only their own cards plus public information (table, trump, scores,
the previous trick). The renderer receives only the redacted view, so it
structurally cannot draw hidden cards.

This is **display privacy, not cryptographic secrecy**: the token still carries
the full state (the opponent's device needs it). A determined player could
decode a token; the agreement is not to. Genuine secrecy is a separate, larger
milestone (§10).

## 3. Scope

### Implemented (through v0.4.0)
- Two players, a **single** game to completion.
- **No following-suit** rule.
- **CLI** with an **ASCII-art board** and manual token import/export.
- Hidden opponent hand + hidden deck contents.
- Automatic per-device identity, remembered per game (§8).
- Per-trick **screen reset** + **last-trick header** (§7).
- **Paste-to-load** as the default menu action (§6).
- Buildable as a **portable single-file executable**.

### Out of scope (deferred — §10)
- Cryptographic secrecy; match play / best-of-N; 4-player / team; following-suit
  variants; colour; GUI; automated token transport.

## 4. Game Rules

### 4.1 Deck & Notation
40-card Italian deck. Suits by first letter: `D` Denari, `S` Spade, `C` Coppe,
`B` Bastoni. Ranks `1`–`10` (1 = Asso … 10 = Re). Card encoding `<SUIT>-<RANK>`
with a delimiter (e.g. `D-1`, `S-10`).

### 4.2 Card Values & Strength — **CRITICAL**
The numeric rank is **neither** the point value **nor** the trick strength; the
engine keeps the three concepts separate and never compares by label.

| Label | Card | Italian | Points | Strength (1 = highest) |
|:-----:|------|---------|:------:|:----------------------:|
| 1  | Ace      | Asso     | 11 | 1  |
| 3  | Three    | Tre      | 10 | 2  |
| 10 | King     | Re       | 4  | 3  |
| 9  | Knight   | Cavallo  | 3  | 4  |
| 8  | Jack     | Fante    | 2  | 5  |
| 7  | Seven    | Sette    | 0  | 6  |
| 6  | Six      | Sei      | 0  | 7  |
| 5  | Five     | Cinque   | 0  | 8  |
| 4  | Four     | Quattro  | 0  | 9  |
| 2  | Two      | Due      | 0  | 10 |

Total 120 points; 61+ wins; 60–60 is a draw (*pareggio*).

### 4.3 Setup, Trick Flow, Draws, End
Deal 3 each; flip the next card for the **briscola** (trump), which sits at the
bottom of the draw pile as the last card drawn. Player 2 leads the first trick.
Each trick: leader plays any card, opponent plays any card. Winner: same suit →
higher strength; one briscola → briscola; two different non-briscola suits →
leader. Winner draws first then loser (flipping the lead). End of deck: the last
draw takes the exposed briscola. Game ends after 20 tricks.

## 5. Architecture

Three modules, cleanly separated:

- **`briscola_engine.py`** — pure logic, no I/O, deterministic. API:
  `new_game(seed)`, `player_view(state, player)`, `legal_moves`, `apply_move`,
  `serialize`/`deserialize`, `is_terminal`, `result`. `apply_move` works on the
  full state; the seed is used once and never stored.
- **`briscola_render.py`** — pure presentation: `player_view` dict → ASCII-art
  text. No I/O, no logic, and it receives only the redacted view, which makes
  the hidden-hand guarantee airtight at the render layer.
- **`briscola_cli.py`** — control flow only: menu, paste-default, identity/
  session, screen reset, input, game loop.

### 5.1 State Model (carried in the token)
`version`, `game_id`, ordered `deck`, `briscola_suit`, `briscola_card`,
`hands` (both), `table` (`[player, card]` entries), **`last_trick`** (`{plays,
winner, points}` or null), `leader`, `turn`, `captured_points`,
`captured_cards`, `trick_no`. The shuffle **seed is not stored**.

### 5.2 Token Format — **version 3**
`state → JSON → zlib → urlsafe base64`, wrapped with an 8-char checksum for
corruption detection (not security). `deserialize` rejects bad checksums and
unsupported versions with clear errors.

### 5.3 `player_view` redaction
Exposes: `you`, `your_hand`, `opponent_hand_count`, `deck_count`, `table`,
`last_trick`, `captured_points/cards`, `turn`, `leader`, `trick_no`,
`briscola_suit`, `briscola_card`, `briscola_in_deck`. Omits the raw `hands` and
`deck` contents. The turned-up briscola card and the last trick are public.

## 6. Interface — CLI

- Menu prompt accepts a **pasted token directly** (the common case), or the
  keys `[1]` new, `[2]` load (explicit paste), `[q]` quit. Detection: known keys
  are commands; otherwise the input is attempted as a token (`deserialize`);
  tokens are long base64 and never collide with the keys.
- New game records this device as Player 1 and prints the opening token.
- Loading auto-assigns identity (§8) and enters the game loop.
- A device plays while it is its turn; when the turn passes it prints a token to
  send and stops.
- Errors handled without crashing: garbled/old token (checksum/version), illegal
  card, out-of-turn move.

## 7. Board Rendering & Per-Trick Reset

- The screen is cleared at the top of each rendered trick view (ANSI clear, with
  a Windows enable-shim; skipped when output is not an interactive terminal so
  pipes/tests stay clean). The token to send is printed *after* the board and is
  never cleared away before the player copies it.
- A one-line **last-trick header** recalls the previous trick (both plays and
  the winner with points), drawn from `last_trick`; the first trick shows
  "game start".
- Cards are ASCII boxes with **5 interior rows**. Italian suit glyphs:
  `(o)` Denari, `\_/` Coppe, `-+>` Spade, `o==` Bastoni. The **trump card** is
  always drawn and labelled `TRUMP (suit)`. The opponent's hand is drawn as
  face-down backs (count only); their played card, when on the table, is shown
  face-up.

## 8. Automatic Identity

A token reaches a player only on their turn, so on **first** sight of a
`game_id` the device adopts `state["turn"]` as its identity and stores it.
Thereafter the stored identity is authoritative (re-pasting a stale token cannot
flip it). Persisted to `~/.briscola_sessions.json` (one entry per active game,
cleared at game end); degrades to in-memory if unwritable.

## 9. Non-Functional Requirements

- **Portable executable:** `PyInstaller --onefile`; stdlib only; the three
  modules bundle into one binary. Built per OS. ASCII-only board renders on
  legacy consoles. The only runtime file is the session file; the app runs
  without it.
- **Quality:** deterministic engine; exact serialize/deserialize round-trips;
  versioned tokens. Test suite (stdlib `unittest`, 45 tests) covers deck/deal,
  all trick-resolution cases, draw order, scoring, end-of-deck briscola draw,
  terminal/result, serialization + tamper rejection, `player_view` redaction,
  `last_trick`, card/board rendering, session store, auto-identity, menu
  parsing, and full randomized + two-device playthroughs.

## 10. Roadmap

- **Real secrecy (next milestone):** encrypted per-player state / mental-poker
  dealing so the token itself does not reveal the opponent's hand or the deck
  order, with no trusted third party. The `player_view` and serialization seams
  absorb this without changing game logic.
- Match play / cumulative scoring; 4-player / team; following-suit variant;
  colour; GUI; automated token transport.

## 11. Glossary
**Briscola** — trump suit (and the game). **Carico** — a high-value card
(Asso/Tre). **Liscio** — a low/zero-point card. **Pareggio** — a 60–60 draw.
**Token** — the base64 string encoding the full game state.
