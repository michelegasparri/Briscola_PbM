"""
Tests for the rendering module (v0.4.0). Stdlib only.

Run:  python -m unittest test_briscola_render -v
"""

import unittest

import briscola_engine as be
import briscola_render as br


class TestCards(unittest.TestCase):
    def test_face_shape(self):
        face = br.card_face("D-1")
        self.assertEqual(len(face), 7)                 # 5 interior rows + 2 borders
        self.assertTrue(all(len(line) == br.CARD_W for line in face))
        self.assertEqual(face[1], "|1    |")           # rank top-left
        self.assertEqual(face[5], "|    1|")           # rank bottom-right
        self.assertEqual(face[3], "| (o) |")           # Denari glyph centered

    def test_face_ten_is_two_digits(self):
        face = br.card_face("S-10")
        self.assertEqual(face[1], "|10   |")
        self.assertEqual(face[5], "|   10|")
        self.assertEqual(face[3], "| -+> |")           # Spade glyph

    def test_all_suit_glyphs_present(self):
        for suit, glyph in br.SUIT_GLYPH.items():
            face = br.card_face(f"{suit}-7")
            self.assertEqual(face[3], f"|{glyph.center(5)}|")

    def test_back_shape_and_distinct(self):
        back = br.card_back()
        self.assertEqual(len(back), 7)
        self.assertTrue(all(len(line) == br.CARD_W for line in back))
        self.assertNotEqual(back, br.card_face("D-1"))


class TestSections(unittest.TestCase):
    def test_last_trick_line_game_start(self):
        v = be.player_view(be.new_game(seed=1), 0)
        self.assertIn("game start", br.last_trick_line(v).lower())

    def test_last_trick_line_formats_winner(self):
        s = be.new_game(seed=1)
        lead = s["turn"]
        s = be.apply_move(s, lead, s["hands"][lead][0])
        s = be.apply_move(s, 1 - lead, s["hands"][1 - lead][0])
        line = br.last_trick_line(be.player_view(s, 0))
        self.assertIn("Last trick", line)
        self.assertIn("wins", line)
        self.assertRegex(line, r"\(\+\d+\)")

    def test_hand_block_has_indices(self):
        v = be.player_view(be.new_game(seed=1), 1)
        block = br.hand_block(v)
        self.assertIn("YOUR HAND:", block[0])
        self.assertIn("[0]", block[-1])
        self.assertIn("[2]", block[-1])


class TestBoard(unittest.TestCase):
    def test_board_sections_present(self):
        v = be.player_view(be.new_game(seed=5), 1)
        board = br.render_board(v)
        for token in ("TRUMP", "OPPONENT (3)", "ON THE TABLE", "YOUR HAND", "Trump:"):
            self.assertIn(token, board)

    def test_board_shows_trump_card(self):
        s = be.new_game(seed=5)
        v = be.player_view(s, 1)
        board = br.render_board(v)
        trump_suit = s["briscola_suit"]
        self.assertIn(be.SUIT_NAMES[trump_suit], board)
        self.assertIn(br.SUIT_GLYPH[trump_suit], board)

    def test_board_renders_for_both_players(self):
        s = be.new_game(seed=9)
        for viewer in (0, 1):
            board = br.render_board(be.player_view(s, viewer))
            self.assertIsInstance(board, str)
            self.assertIn("YOUR HAND", board)


if __name__ == "__main__":
    unittest.main(verbosity=2)
