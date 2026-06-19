# Briscola (String-Passing) — Specification v0.3

*Supersedes the v0.1 spec. Reflects what is actually implemented.*

## 1. Purpose & Concept

A two-player, serverless implementation of the Italian card game **Briscola**.
There is no live connection and no central server: the **complete game state is
serialized into a single string ("token")** that players exchange manually
(chat, email, etc.). The token *is* the source of truth and the save file.

Turns are asynchronous: a player loads the latest token, makes a move, and the
program emits a new token to send to the opponent.

## 2. Trust Model

**Honor system with interface-level hiding.** As of v0.3 the opponent's hand and
the deck's upcoming cards are redacted from everything the program displays
(via `player_view`); a player only ever sees their own cards plus public
information (table, scores, trump, turn).

This is **display privacy, not cryptographic secrecy.** The token still carries
the full state, because the opponent's device needs it to keep playing. A
determined player could decode a token and read the hidden cards; the agreement
is not to. Genuine secrecy is a separate, larger milestone (§9).

## 3. Scope

### Implemented (through v0.3)
- Two players, a **single** game to completion.
- **No following-suit** rule (any card may be played).
- **CLI** interface with manual token import/export and card selection.
- **Hidden opponent hand + hidden deck contents** at the interface.
- **Automatic per-device identity**, remembered per game (§7).
- Buildable as a **portable single-file executable**.

### Out of scope (deferred — see §9)
- Cryptographic secrecy (encryption / mental poker).
- Match play / best-of-N, 4-player / team play.
- Following-suit variants, GUI, animation, automated token transport.

## 4. Game Rules

### 4.1 Deck & Notation
- 40-card Italian deck. Suits by first letter: `D` Denari, `S` Spade,
  `C` Coppe, `B` Bastoni. Ranks `1`–`10` (1 = Asso … 10 = Re).
- Card encoding: `<SUIT>-<RANK>` with a delimiter — e.g. `D-1`, `S-10`, `B-9`
  (the delimiter is required because rank `10` is two digits).

### 4.2 Card Values & Strength — **CRITICAL**
The numeric rank is **neither** the point value **nor** the trick strength. The
engine keeps three separate concepts (label, points, strength) and never
compares cards by their numeric label.

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

Total points = **120**. 61+ wins; 60–60 is a draw (*pareggio*).

### 4.3 Setup
Shuffle; deal 3 cards each; flip the next card — its suit is the **briscola**
(trump), and it sits at the bottom of the draw pile as the last card drawn. The
non-starting player (Player 2) leads the first trick.

### 4.4 Trick Flow & Resolution
Leader plays a card, opponent plays any card. Winner:
- same suit → higher **strength** wins;
- one card is briscola, the other isn't → briscola wins;
- two different non-briscola suits → the **leader** wins.

### 4.5 Draws & End
Trick winner draws first, then the loser (this flips who leads next). End of
deck: the second-to-last draw takes the last face-down card; the final draw
takes the exposed briscola card. Game ends after all 40 cards are played (20
tricks).

## 5. Architecture

Strict separation between a **pure engine** (no I/O, deterministic) and the
**CLI**. All display routes through `player_view`.

### 5.1 Engine API
- `new_game(seed) -> State`
- `player_view(state, player) -> view` — **redacts** the opponent's hand
  (count only) and deck contents (count only); exposes the viewer's hand and
  public info. This is the seam that lets cryptographic hiding be added later
  without touching game logic.
- `legal_moves(state, player)` — any card in hand (no following-suit rule).
- `apply_move(state, player, card) -> State` — operates on the full state.
- `serialize(state) -> token` / `deserialize(token) -> State`
- `is_terminal(state)` / `result(state)`

### 5.2 State Model (carried in the token)
`version`, `game_id`, ordered `deck`, `briscola_suit`, `briscola_card`,
`hands` (both), `table` (`[player, card]` entries), `captured_points`,
`captured_cards`, `turn`, `leader`, `trick_no`. The shuffle **seed is not
stored** (storing it would let the opponent reproduce the deck order).

### 5.3 Token Format — **version 2**
`state → JSON → zlib → urlsafe base64`, wrapped with an 8-char checksum for
corruption detection (not security). `deserialize` rejects bad checksums and
unsupported versions with clear errors. v1 tokens (no `game_id`) are rejected.

### 5.4 `player_view` redaction (v0.3)
The view contains: `you`, `your_hand`, `opponent_hand_count`, `deck_count`,
`table`, `captured_points/cards`, `turn`, `leader`, `trick_no`, `briscola_suit`,
`briscola_card`, `briscola_in_deck`. It deliberately omits the raw `hands` list
and the `deck` contents. The turned-up briscola card is public (both players
see it) and remains shown.

## 6. Interface — CLI

- Menu: New game / Load token / Quit.
- New game: creates the opening token, records this device as Player 1.
- Load token: paste → validate → auto-assign identity (§7) → play.
- A device plays while it is its turn; when the turn passes, it prints a token
  to send and stops. Display shows only the viewer's hand; the opponent's is a
  hidden count.
- Errors handled without crashing: garbled/truncated token (checksum),
  unsupported version, illegal card, out-of-turn move.

## 7. Automatic Identity (v0.2)

A token is only ever sent to a player when it is their turn, so on **first**
import a device adopts `state["turn"]` as its identity and stores it, keyed by
`game_id`. Afterwards the stored identity is authoritative and is never
re-derived (re-pasting a stale token cannot flip who you are). Identity persists
to `~/.briscola_sessions.json` (one entry per active game, cleared at game end),
surviving relaunches between turns; if the file can't be written, it degrades to
in-memory for the session.

## 8. Non-Functional Requirements

- **Portable executable:** `PyInstaller --onefile`; stdlib only, so the binary
  stays small. "Portable" = no Python needed on the target, built per OS (not
  one binary for all platforms). The only runtime file touched is the session
  file in the user's home dir; the app runs without it.
- **Quality:** engine is deterministic; `serialize`/`deserialize` round-trips
  exactly; token format is versioned. Test suite (stdlib `unittest`) covers
  deck/deal, all trick-resolution cases, draw order, scoring, end-of-deck
  briscola draw, terminal/result, serialization + tamper rejection,
  `player_view` redaction, session store, auto-identity, and full randomized +
  two-device playthroughs.

## 9. Roadmap

- **Real secrecy (next milestone):** replace display-level hiding with encrypted
  per-player state / mental-poker dealing, so the token itself does not reveal
  the opponent's hand or the deck order, with no trusted third party. The
  `player_view` and serialization seams are designed to absorb this without
  changing game logic.
- Match play / cumulative scoring; 4-player / team Briscola; following-suit
  variant; GUI + animation; automated token transport.

## 10. Glossary
**Briscola** — the trump suit (and the game). **Carico** — a high-value card
(Asso/Tre). **Liscio** — a low/zero-point card. **Pareggio** — a 60–60 draw.
**Token** — the base64 string encoding the full game state.
