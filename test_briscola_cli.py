"""
Tests for the CLI's automatic-identity layer (v0.2). Stdlib only.

Run:  python -m unittest test_briscola_cli -v
"""

import os
import random
import tempfile
import unittest

import briscola_engine as be
import briscola_cli as cli


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_set_get_clear(self):
        s = cli.SessionStore(path=self.path)
        self.assertIsNone(s.get("game-x"))
        s.set("game-x", 1)
        self.assertEqual(s.get("game-x"), 1)
        s.clear("game-x")
        self.assertIsNone(s.get("game-x"))

    def test_persists_across_instances(self):
        cli.SessionStore(path=self.path).set("g1", 0)
        # a fresh instance (e.g. app relaunched) reads the same identity
        self.assertEqual(cli.SessionStore(path=self.path).get("g1"), 0)

    def test_missing_file_is_empty(self):
        s = cli.SessionStore(path=self.path + ".does-not-exist")
        self.assertIsNone(s.get("anything"))


class TestResolveIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_first_import_adopts_turn(self):
        s = cli.SessionStore(path=self.path)
        state = be.new_game(seed=7)          # Player 2's turn (turn == 1)
        player, is_new = cli.resolve_identity(s, state)
        self.assertTrue(is_new)
        self.assertEqual(player, state["turn"])

    def test_identity_is_locked_after_first(self):
        s = cli.SessionStore(path=self.path)
        state = be.new_game(seed=7)
        first, _ = cli.resolve_identity(s, state)
        # later the same device sees a token where it is the OTHER player's turn
        state2 = dict(state)
        state2["turn"] = 1 - first
        player, is_new = cli.resolve_identity(s, state2)
        self.assertFalse(is_new)
        self.assertEqual(player, first)        # identity did not flip


class TestTwoDeviceGame(unittest.TestCase):
    def _store(self):
        t = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        t.close()
        self.addCleanup(lambda p=t.name: os.path.exists(p) and os.unlink(p))
        return cli.SessionStore(path=t.name)

    def test_full_game_two_devices(self):
        dev = {0: self._store(), 1: self._store()}   # device A = P1, device B = P2
        rng = random.Random(123)

        state = be.new_game(seed=42)
        gid = state["game_id"]
        dev[0].set(gid, 0)                            # creator records Player 1
        token = be.serialize(state)

        joined_b = False
        guard = 0
        while True:
            s = be.deserialize(token)
            if be.is_terminal(s):
                break
            turn = s["turn"]
            player, is_new = cli.resolve_identity(dev[turn], s)
            self.assertEqual(player, turn)            # auto-identity matches the turn
            if turn == 1 and is_new:
                joined_b = True                       # B auto-joined as Player 2
            # play out this device's consecutive turns, then hand off
            while s["turn"] == player and not be.is_terminal(s):
                s = be.apply_move(s, player, rng.choice(be.legal_moves(s, player)))
            token = be.serialize(s)
            guard += 1
            self.assertLess(guard, 1000)

        self.assertTrue(joined_b)
        self.assertEqual(dev[0].get(gid), 0)
        self.assertEqual(dev[1].get(gid), 1)
        final = be.result(be.deserialize(token))
        self.assertEqual(sum(final["points"]), 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
