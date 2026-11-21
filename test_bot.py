"""Local regression tests; run with `python -m unittest -v test_bot`."""
import gzip
import json
import math
import os
import unittest

from arena import Arena
from strategy import SurvivalPolicy
from weapons import mortar_solution, predict_gun_lead, WeaponController


ROOT = os.path.dirname(__file__)
KIT = os.path.join(os.path.dirname(ROOT), "mechfight-kit")


class GeometryTests(unittest.TestCase):
    def test_gun_leads_moving_target(self):
        point, _, flight = predict_gun_lead([0, 0, 7], [100, 0, 4.5], [0, 12, 0], 252)
        self.assertGreater(flight, 0.35)
        self.assertAlmostEqual(point[1], 12 * flight, places=5)

    def test_mortar_ballistics(self):
        solution = mortar_solution([0, 0, 9.5], [100, 0, 0], 72, 22)
        self.assertIsNotNone(solution)
        yaw, pitch, flight = solution
        self.assertAlmostEqual(yaw, 0)
        self.assertGreater(pitch, 0)
        vx, vz = 72 * math.cos(pitch), 72 * math.sin(pitch)
        z = 9.5 + vz * flight - 0.5 * 22 * flight * flight
        self.assertAlmostEqual(vx * flight, 100, places=6)
        self.assertAlmostEqual(z, 0, places=6)


class WeaponIntegrationTests(unittest.TestCase):
    def test_aligned_weapons_fire_in_open_ground(self):
        stream = os.path.join(KIT, "check", "stream.jsonl.gz")
        if not os.path.isfile(stream):
            self.skipTest("development kit replay is not present")
        with gzip.open(stream, "rt", encoding="utf-8") as f:
            config = json.loads(next(f))["config"]
        for kind in ("gun", "laser", "mortar", "lightning"):
            with self.subTest(kind=kind):
                bot = SurvivalPolicy({"map": {"dir": os.path.join(KIT, "arena")},
                                      "config": config, "seed": 1, "slot": 1})
                gun = {"kind": "gun", "cooldown": 0, "ammo": 12, "reload": 0,
                       "stats": config["weapons"]["gun"]}
                special = {"kind": kind, "cooldown": 0, "stats": config["weapons"][kind]}
                if kind == "laser":
                    special["charge"] = 0.8
                y = 35 if kind == "lightning" else 100
                me = {"id": 1, "pos": [100, 0, bot.arena.height(100, 0)],
                      "vel": [0, 0, 0], "aim": [math.pi / 2, 0],
                      "hp": 1400, "max_hp": 1400, "energy": 100, "max_energy": 100,
                      "grounded": True, "cubes": 0, "upgrades": [],
                      "weapons": [gun, None if kind == "gun" else special],
                      "in_zone": True, "stats": dict(config["mech"])}
                enemy = {"id": 4, "kind": "mech",
                         "pos": [100, y, bot.arena.height(100, y)],
                         "vel": [0, 0, 0], "hp": 1400, "max_hp": 1400, "cubes": 0}
                me["aim"] = bot.weapons.act({"self": me}, enemy, True)["aim"]
                obs = {"type": "obs", "tick": 0, "t": 0, "alive": 16, "self": me,
                       "mechs": [enemy], "projectiles": [], "crates": [], "cubes": [],
                       "pickups": [], "sounds": [], "beams": [], "events": [],
                       "zone": {"center": [0, 0], "radius": 560, "next_center": [0, 0],
                                "next_radius": 380, "shrink_start": 60,
                                "shrink_end": 110, "dps": 20},
                       "offer": None, "drops": []}
                action = bot.act(obs)
                self.assertTrue(any(action["fire"]), action)


class ReplayTests(unittest.TestCase):
    def test_real_observation_replay(self):
        stream = os.path.join(KIT, "check", "stream.jsonl.gz")
        if not os.path.isfile(stream):
            self.skipTest("development kit replay is not present")
        with gzip.open(stream, "rt", encoding="utf-8") as f:
            hello = json.loads(next(f))
            hello["map"]["dir"] = os.path.join(KIT, "arena")
            bot = SurvivalPolicy(hello)
            shots = 0
            for line in f:
                obs = json.loads(line)
                if obs.get("type") != "obs":
                    continue
                action = bot.act(obs)
                self.assertEqual(action["tick"], obs["tick"])
                self.assertLessEqual(math.hypot(*action["move"]), 1.000001)
                self.assertTrue(all(math.isfinite(x) for x in action["aim"]))
                self.assertEqual(len(action["fire"]), 2)
                shots += sum(action["fire"])
            self.assertGreater(shots, 0, "bot must return fire during replay")

    def test_ceasefire_still_faces_attacker(self):
        stream = os.path.join(KIT, "check", "stream.jsonl.gz")
        if not os.path.isfile(stream):
            self.skipTest("development kit replay is not present")
        with gzip.open(stream, "rt", encoding="utf-8") as f:
            hello = json.loads(next(f))
            hello["map"]["dir"] = os.path.join(KIT, "arena")
            bot = SurvivalPolicy(hello)
            for line in f:
                obs = json.loads(line)
                if obs.get("type") != "obs":
                    continue
                if obs["t"] >= 10:
                    action = bot.act(obs)
                    self.assertEqual(action["fire"], [False, False])
                    self.assertIn("aim", action)
                    return
        self.fail("no observation reached ceasefire test")


if __name__ == "__main__":
    unittest.main()
