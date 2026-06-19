# Briscola (String-Passing, Honor-System) — Specification v0.1

## 1. Purpose & Concept

A two-player, serverless implementation of the Italian card game **Briscola**.
There is no live connection and no central server: the **complete game state is
serialized into a single string ("token")** that players exchange manually (chat,
email, etc.). The token *is* the source of truth and the save file.

Turns are asynchronous: a player loads the latest token, makes a move, and the
program emits a new token to send to the opponent.

**Trust model: honor system.** v0.1 makes no attempt to hide information
cryptographically. The token carries the full state; players simply agree not to
inspect the parts that aren't theirs. (See §9 for the planned upgrade path.)

---

## 2. Scope

### In scope (v0.1)
- Two players only.
- A **single** game to completion (no match / best-of-N).
- **No following-suit** rule — a player may play any card from hand.
- **CLI** interface.
- **Full view** for v0.1: both hands are shown (no hidden information yet).
- Manual token import/export and card selection.
- Final deliverable buildable as a **portable single-file executable**.

### Out of scope (deferred — see §9)
- Real secrecy (encryption / mental poker), hidden hands.
- Match play, scorekeeping across games.
- 4-player / team play.
- Following-suit variants (e.g. enforced once the deck is exhausted).
- GUI, animation, automated token transport / networking.

---

## 3. Game Rules (agreed variant)

### 3.1 Deck & Notation
- 40-card Italian deck, four suits, ten ranks each.
- **Suit notation** — Italian first letter:
  - `D` = Denari, `S` = Spade, `C` = Coppe, `B` = Bastoni
- **Rank notation** — numeric `1`–`10`, mapped onto the physical cards.
- **Card encoding:** `<SUIT>-<RANK>` with a delimiter, e.g. `D-1`, `S-10`,
  `C-7`, `B-9`. (Delimiter is required because rank `10` is two digits.)

### 3.2 Card Values & Strength — **CRITICAL**
The numeric label is **neither** the point value **nor** the trick strength.
The engine MUST keep three separate concepts per card (label, points, strength)
and must **never** compare or sort cards by their numeric label.

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

Traps to watch: the **3** is the 2nd-strongest card and worth 10 points; the
**10 (Re)** is only 3rd-strongest and worth 4; the **2** is the weakest card.
Total points in the deck = **120**.

### 3.3 Setup / Initialization
1. Shuffle the 40 cards (see §6 for seed handling).
2. Deal **3 cards** to each player.
3. Flip the next card from the deck — its suit becomes the **briscola** (trump).
   This exposed card sits at the bottom of the draw pile and is the **last** card
   drawn.
4. The non-starting player leads the first trick (convention; see §5 identity).

### 3.4 Trick Flow
- The leader plays one card; the opponent then plays one card (any card — no
  following-suit obligation).
- **Trick resolution:**
  - Both same suit → higher **strength** wins.
  - One card is briscola, the other isn't → briscola wins.
  - Two different non-briscola suits → the **leader's** card wins.
- Winner takes both cards into their capture pile and scores their points.

### 3.5 Draw Rules
- After each trick the **winner draws first**, then the loser. (This flips who
  leads the next trick — the trick winner leads next.)
- End of deck: the second-to-last draw takes the last face-down card; the final
  draw takes the **exposed briscola card**.
- Once the deck is empty, players continue playing out their remaining hands.

### 3.6 End & Win Condition
- Game ends when all 40 cards have been played (20 tricks).
- **61+ points wins.** 60–60 is a draw (*pareggio*).

---

## 4. Architecture

Strict separation between **game engine** (pure logic, no I/O) and **interface**
(CLI). This keeps the engine reusable for a future GUI and unit-testable.

### 4.1 Engine API (UI-agnostic, pure, deterministic)
- `new_game(seed) -> State`
- `player_view(state, player) -> view` — returns what a player may see. **In
  v0.1 it returns the full state** (full view), but all display MUST route
  through it so hidden-hand support is a drop-in later.
- `legal_moves(state, player) -> [card]` — v0.1: any card in the player's hand.
- `apply_move(state, player, card) -> State`
- `serialize(state) -> token`
- `deserialize(token) -> State`
- `is_terminal(state) -> bool`
- `result(state) -> (winner | draw, points_p0, points_p1)`

The engine performs no I/O and is deterministic given its inputs.

### 4.2 State Model (what the token carries)
- `version` — token/format schema version.
- `deck` — ordered list of remaining cards (face-down draw order).
- `briscola_suit`, `briscola_card` — trump suit and the exposed last card.
- `hands` — `[[...], [...]]`, one list per player.
- `table` — card(s) played in the current trick plus who led.
- `captured` — captured points (and/or captured cards) per player.
- `turn` — whose turn it is (0 or 1).
- `leader` — who leads the current trick.
- `trick_no` / `phase`.
- `checksum` — corruption detection (copy/paste truncation), not security.
- *(optional)* `prev_token_hash` — detect replayed / out-of-order tokens.
- **NOT** the shuffle seed (see §6).

### 4.3 Token Format
`state (dict) → JSON → zlib compress → base64 → token string`

- Always include the `version` field and a `checksum` so a garbled paste fails
  cleanly rather than corrupting a game.
- Format is opaque to players in practice but is **not** secure — it is encoding,
  not encryption.

---

## 5. Interface — CLI (v0.1)

### 5.1 Flows
- **Main menu:** New Game / Load Token / Quit.
- **New Game:** start a fresh game, emit the first token (§7).
- **Load Token:** paste a token → validate → show full view → play.
- **Play:** display the view, prompt the current player to choose a card from
  hand, validate, apply, resolve trick / draws if needed, then **print the new
  token to copy** and send to the opponent.
- **Terminal:** print final points and result (win / draw).

### 5.2 Full-View Display (v0.1)
Show both hands, the table, the briscola (suit + exposed card), remaining deck
count, captured points per player, and whose turn it is.

### 5.3 Player Identity
Each client knows which player it is (chosen at new-game / load time). The client
**refuses to move when the token says it is not that player's turn**. No
persistent identity storage is required in v0.1.

### 5.4 Error Handling (no crashes)
- Malformed / truncated token → checksum failure → clear message, return to menu.
- Illegal card (not in hand) → re-prompt.
- Out-of-turn move → reject with explanation.
- Wrong-version token → explain and refuse.

---

## 6. Seed Handling

- The seed provides **initialization entropy only** — it is not a fairness or
  secrecy mechanism.
- Acceptable source: `secrets` / `random.SystemRandom`, or a timestamp combined
  with a random salt (a bare timestamp is low-entropy and collision-prone).
- Used **once** inside `new_game(seed)` to shuffle, then **discarded**.
- The seed is **never serialized into the token** — if it were, the opponent
  could reproduce the shuffle and reconstruct the entire deck order.

---

## 7. Initialization Flow (agreed)

1. Player A selects **New Game**, identifies as Player 1.
2. Engine runs `new_game(seed)` → produces the **first token**.
3. A sends the token to Player B out of band (chat/email).
4. B selects **Load Token**, identifies as Player 2, plays when it is their turn,
   emits a new token, sends it back to A.
5. Repeat until the game is terminal.

---

## 8. Non-Functional Requirements

### 8.1 Portable Executable
- Final deliverable builds to a **single-file executable** via
  `PyInstaller --onefile` (Nuitka is an acceptable alternative).
- **Stdlib only** for v0.1 (`json`, `zlib`, `base64`, `hashlib`, `secrets` /
  `random`, plus `cmd`/`argparse` for the CLI). No third-party runtime deps keeps
  the binary small and the build trivial.
- **Platform note:** "portable" means *no Python install needed on the target* —
  not one binary for all OSes. Build separately per platform (Windows `.exe`,
  Linux, macOS).
- **No required runtime files:** the token is the only state and is passed via
  paste/stdin. If any optional local file is later added, resolve paths using the
  frozen-app convention (`sys.frozen` / `sys._MEIPASS`) and write to a
  user-writable directory, not the bundle.

### 8.2 Quality
- Engine is deterministic given `(state, move)` → reproducible, testable.
- `serialize`/`deserialize` must round-trip exactly.
- Unit tests for: deal, trick resolution (all four cases), draw order, scoring,
  end-of-deck briscola draw, terminal detection, win/draw result.
- Token format is **versioned from day one**; unknown versions fail gracefully.

---

## 9. Future / Upgrade Path

- **Real secrecy:** swap the honor system for encryption / mental-poker-style
  protocols. Because all display already routes through `player_view` and all
  transport through `serialize`/`deserialize`, this can be added **without
  touching core game logic**. This is the key reason for the engine/interface
  seam in v0.1.
- Hidden hands (real `player_view` filtering).
- Match play / cumulative scoring.
- 4-player / team Briscola.
- Following-suit variant (e.g. enforced once the deck is exhausted).
- GUI + animation, automated token transport.

---

## 10. Glossary

- **Briscola** — the trump suit (and the name of the game). Set by the card
  flipped at deal time.
- **Carico** — a high-value card (Asso / Tre).
- **Liscio** — a low/zero-point card.
- **Pareggio** — a 60–60 draw.
- **Token** — the base64 string encoding the full game state.
