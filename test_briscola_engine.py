"""
Unit tests for the Briscola engine. Stdlib only.

Run:  python -m unittest test_briscola_engine -v
"""

import random
import re
import unittest

import briscola_engine as be


class TestDeck(unittest.TestCase):
    def test_deck_composition(self):
        deck = be.full_deck()
        self.assertEqual(len(deck), 40)
        self.assertEqual(len(set(deck)), 40)

    def test_total_points_is_120(self):
        total = sum(be.card_points(c) for c in be.full_deck())
        self.assertEqual(total, 120)


class TestDeal(unittest.TestCase):
    def test_new_game_layout(self):
        s = be.new_game(seed=42)
        self.assertEqual(len(s["hands"][0]), 3)
        self.assertEqual(len(s["hands"][1]), 3)
        self.assertEqual(len(s["deck"]), 34)
        # briscola suit matches the exposed bottom card
        self.assertEqual(s["briscola_suit"], be.card_suit(s["deck"][-1]))
        self.assertEqual(s["briscola_card"], s["deck"][-1])
        # non-starting player leads first
        self.assertEqual(s["leader"], 1)
        self.assertEqual(s["turn"], 1)
        # all 40 cards accounted for, no duplicates
        seen = s["hands"][0] + s["hands"][1] + s["deck"]
        self.assertEqual(len(seen), 40)
        self.assertEqual(len(set(seen)), 40)

    def test_seed_not_in_state(self):
        s = be.new_game(seed=42)
        self.assertNotIn("seed", s)


class TestTrickResolution(unittest.TestCase):
    def test_same_suit_higher_strength_wins(self):
        # Tre (rank 3, strength 2) beats Re (rank 10, strength 3) in the same suit
        table = [[0, "C-10"], [1, "C-3"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 1)

    def test_same_suit_ace_beats_three(self):
        table = [[0, "C-3"], [1, "C-1"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 1)

    def test_briscola_beats_higher_offsuit(self):
        # responder's low briscola beats leader's Asso of another suit
        table = [[0, "C-1"], [1, "D-2"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 1)

    def test_leader_briscola_beats_responder_offsuit(self):
        table = [[0, "D-4"], [1, "C-1"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 0)

    def test_different_offsuit_leader_wins(self):
        # neither is briscola and suits differ -> leader wins even with a weaker card
        table = [[0, "C-2"], [1, "S-1"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 0)

    def test_both_briscola_higher_strength_wins(self):
        table = [[0, "D-8"], [1, "D-1"]]
        self.assertEqual(be.resolve_trick(table, briscola_suit="D"), 1)


class TestApplyMove(unittest.TestCase):
    def test_first_card_passes_turn(self):
        s = be.new_game(seed=7)
        card = s["hands"][1][0]
        s2 = be.apply_move(s, 1, card)
        self.assertEqual(len(s2["table"]), 1)
        self.assertEqual(s2["turn"], 0)
        self.assertNotIn(card, s2["hands"][1])

    def test_out_of_turn_rejected(self):
        s = be.new_game(seed=7)
        with self.assertRaises(be.IllegalMove):
            be.apply_move(s, 0, s["hands"][0][0])

    def test_card_not_in_hand_rejected(self):
        s = be.new_game(seed=7)
        not_held = next(c for c in be.full_deck() if c not in s["hands"][1])
        with self.assertRaises(be.IllegalMove):
            be.apply_move(s, 1, not_held)

    def test_winner_draws_first_and_leads(self):
        # build a controlled mini-state to verify draw order + lead handoff
        s = be.new_game(seed=1)
        s["hands"] = [["C-2"], ["D-1"]]          # player 1 (briscola) will win
        s["deck"] = ["S-5", "S-6"]               # winner draws S-5, loser draws S-6
        s["briscola_suit"] = "D"
        s["leader"] = 0
        s["turn"] = 0
        s["captured_points"] = [0, 0]
        s["captured_cards"] = [0, 0]
        s = be.apply_move(s, 0, "C-2")           # leader plays
        s = be.apply_move(s, 1, "D-1")           # responder plays briscola, wins
        self.assertEqual(s["leader"], 1)
        self.assertEqual(s["turn"], 1)
        self.assertEqual(s["hands"][1], ["S-5"])  # winner drew first
        self.assertEqual(s["hands"][0], ["S-6"])  # loser drew second
        self.assertEqual(s["captured_points"][1], 11)
        self.assertEqual(s["captured_cards"][1], 2)


class TestSerialization(unittest.TestCase):
    def test_round_trip(self):
        s = be.new_game(seed=99)
        s2 = be.deserialize(be.serialize(s))
        self.assertEqual(s, s2)

    def test_round_trip_midgame(self):
        s = be.new_game(seed=99)
        s = be.apply_move(s, 1, s["hands"][1][0])
        token = be.serialize(s)
        self.assertEqual(be.deserialize(token), s)

    def test_corrupted_token_raises(self):
        token = be.serialize(be.new_game(seed=99))
        # flip a character in the middle
        i = len(token) // 2
        flipped = "A" if token[i] != "A" else "B"
        bad = token[:i] + flipped + token[i + 1:]
        with self.assertRaises(be.TokenError):
            be.deserialize(bad)

    def test_garbage_token_raises(self):
        with self.assertRaises(be.TokenError):
            be.deserialize("not-a-real-token!!!")


class TestFullGame(unittest.TestCase):
    def test_random_playthrough(self):
        rng = random.Random(2024)
        for game in range(200):
            s = be.new_game(seed=rng.random())
            guard = 0
            while not be.is_terminal(s):
                p = s["turn"]
                moves = be.legal_moves(s, p)
                self.assertTrue(moves)
                s = be.apply_move(s, p, rng.choice(moves))
                guard += 1
                self.assertLess(guard, 100, "game did not terminate")
            # invariants at game end
            self.assertEqual(sum(s["captured_cards"]), 40)
            self.assertEqual(sum(s["captured_points"]), 120)
            self.assertEqual(s["hands"], [[], []])
            self.assertEqual(s["deck"], [])
            r = be.result(s)
            self.assertEqual(sum(r["points"]), 120)


def _cards_in(obj):
    """Collect every exact card token (e.g. 'D-7') appearing in a structure."""
    found = set()

    def walk(o):
        if isinstance(o, str):
            if re.match(r"^[DSCB]-(?:[1-9]|10)$", o):
                found.add(o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)

    walk(obj)
    return found


class TestPlayerView(unittest.TestCase):
    def test_hides_opponent_hand(self):
        s = be.new_game(seed=42)
        viewer = 1
        opp_hand = set(s["hands"][1 - viewer])
        v = be.player_view(s, viewer)
        self.assertNotIn("hands", v)                      # no raw both-hands blob
        self.assertEqual(v["your_hand"], s["hands"][viewer])
        self.assertEqual(v["opponent_hand_count"], len(opp_hand))
        # the only card tokens anywhere in the view are the viewer's own hand
        # plus the public turned-up briscola (the table is empty at game start)
        expected = set(s["hands"][viewer]) | {s["briscola_card"]}
        self.assertEqual(_cards_in(v), expected)
        self.assertFalse(opp_hand & _cards_in(v))         # no opponent card leaks

    def test_hides_deck_contents(self):
        s = be.new_game(seed=42)
        v = be.player_view(s, 0)
        self.assertNotIn("deck", v)
        self.assertEqual(v["deck_count"], len(s["deck"]))

    def test_public_info_visible(self):
        s = be.new_game(seed=42)
        v = be.player_view(s, 1)
        self.assertEqual(v["briscola_suit"], s["briscola_suit"])
        self.assertEqual(v["turn"], s["turn"])
        self.assertEqual(v["captured_points"], s["captured_points"])
        self.assertTrue(v["briscola_in_deck"])            # still in the deck at start

    def test_table_cards_are_public(self):
        s = be.new_game(seed=42)                          # Player 2 (index 1) leads
        card = s["hands"][1][0]
        s = be.apply_move(s, 1, card)
        v = be.player_view(s, 0)                          # opponent sees the led card
        self.assertEqual(v["table"], [[1, card]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
