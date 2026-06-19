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

    def test_face_ten_numeric_mode(self):
        old = br.SHOW_FIGURES_AS_LETTERS
        br.SHOW_FIGURES_AS_LETTERS = False
        try:
            face = br.card_face("S-10")
            self.assertEqual(face[1], "|10   |")
            self.assertEqual(face[5], "|   10|")
            self.assertEqual(face[3], "| -+> |")          # Spade glyph
        finally:
            br.SHOW_FIGURES_AS_LETTERS = old

    def test_face_figures_default(self):
        # default mode shows 10/9/8 as K/Q/J; pip cards stay numeric
        self.assertEqual(br.card_face("S-10")[1], "|K    |")
        self.assertEqual(br.card_face("S-10")[5], "|    K|")
        self.assertEqual(br.card_face("C-9")[1], "|Q    |")
        self.assertEqual(br.card_face("B-8")[1], "|J    |")
        self.assertEqual(br.card_face("D-7")[1], "|7    |")

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


class TestFigureSetting(unittest.TestCase):
    def test_default_is_letters(self):
        self.assertTrue(br.SHOW_FIGURES_AS_LETTERS)
        self.assertEqual(br.rank_label(10), "K")
        self.assertEqual(br.rank_label(9), "Q")
        self.assertEqual(br.rank_label(8), "J")

    def test_rank_label_figures(self):
        self.assertEqual(br.rank_label(10, figures=True), "K")
        self.assertEqual(br.rank_label(9, figures=True), "Q")
        self.assertEqual(br.rank_label(8, figures=True), "J")
        self.assertEqual(br.rank_label(7, figures=True), "7")   # pip unchanged
        self.assertEqual(br.rank_label(1, figures=True), "1")

    def test_rank_label_numeric(self):
        for r in (8, 9, 10):
            self.assertEqual(br.rank_label(r, figures=False), str(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
