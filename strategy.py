"""Survival, looting and navigation policy for the Mech Royale bot."""
from __future__ import annotations

import math
import random

from arena import Arena
from weapons import WeaponController


UPGRADE_PRIORITY = {
    "nanites": 100, "armor": 96, "plating": 94, "sensors": 88,
    "gyros": 84, "laser_charge": 82, "laser_damage": 81,
    "gun_damage": 79, "gun_rate": 78, "gun_velocity": 72,
    "gun_mag": 70, "lightning_efficiency": 69, "lightning_range": 68,
    "mortar_splash": 65, "mortar_reload": 64, "reactor": 61,
    "capacitor": 58, "jets": 57, "servos": 55,
    "lightning_chain": 45, "mortar_velocity": 42, "laser_pierce": 40,
}
WEAPON_RANK = {"gun": 0, "lightning": 1, "mortar": 2, "laser": 3}


def distance2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(x, y):
    length = math.hypot(x, y)
    return (x / length, y / length) if length > 1e-8 else (1.0, 0.0)


def clamp_to_circle(point, center, radius):
    dx, dy = point[0] - center[0], point[1] - center[1]
    d = math.hypot(dx, dy)
    if d <= radius or d < 1e-8:
        return [point[0], point[1]]
    return [center[0] + dx * radius / d, center[1] + dy * radius / d]


class SurvivalPolicy:
    def __init__(self, hello):
        self.arena = Arena(hello["map"]["dir"])
        self.weapons = WeaponController(hello["config"])
        self.rng = random.Random(hello.get("seed", 1))
        self.slot = int(hello.get("slot", 0))
        self.phase = self.rng.random() * math.tau
        self.strafe = 1 if self.rng.random() < 0.5 else -1
        self.last_strafe_change = 0.0
        self.last_damage_t = -100.0
        self.last_enemy_t = -100.0
        self.last_pos = None
        self.stuck_since = None
        self.stuck_until = -1.0
        self.last_route_t = -100.0
        self.route_goal = None
        self.route = []
        self.goal_kind = "zone"
        self.safe_goal = None
        self.safe_zone_key = None
        self.loot = {}
        self.cubes = {}
        self.threat_memory = {}
        self.sound_threat = None
        self.last_dodge_t = -100.0
        self.boosting = False
        self.last_combat_t = -100.0
        self.retreat_until = -100.0

    def _remember(self, obs):
        t = obs["t"]
        me = obs["self"]
        for p in obs.get("pickups", []):
            self.loot[p["id"]] = (p["kind"], p["pos"], t)
        for c in obs.get("cubes", []):
            self.cubes[c["id"]] = (c["pos"], t)
        self.loot = {k: v for k, v in self.loot.items() if t - v[2] < 75}
        self.cubes = {k: v for k, v in self.cubes.items() if t - v[1] < 30}
        for e in obs["events"]:
            if e["type"] == "damaged" and e.get("weapon") != "zone":
                self.last_damage_t = t
                if e.get("by") is not None and e["by"] in self.threat_memory:
                    pos, _, old_t = self.threat_memory[e["by"]]
                    self.threat_memory[e["by"]] = (pos, t, old_t)
                elif e.get("bearing") is not None:
                    # Used only as a short-lived escape hint, never as a target.
                    a = e["bearing"]
                    self.sound_threat = ([me["pos"][0] + 65 * math.cos(a),
                                          me["pos"][1] + 65 * math.sin(a)], t)
            elif e["type"] in ("took", "dropped"):
                self.loot.pop(e.get("id"), None)
            elif e["type"] == "take_failed" and e.get("reason") == "gone":
                self.loot.pop(e.get("id"), None)
        for m in obs["mechs"]:
            if m["kind"] == "mech":
                self.last_enemy_t = t
                self.threat_memory[m["id"]] = (m["pos"], t, m.get("hp", 1000))
        self.threat_memory = {k: v for k, v in self.threat_memory.items() if t - v[1] < 5.5}
        for s in obs.get("sounds", []):
            if s["dist"] == "far" or s.get("age", 0) > 1.2:
                continue
            if s["kind"] not in ("gun", "laser", "laser_charge", "mortar", "lightning", "step", "boost"):
                continue
            d = 45 if s["dist"] == "near" else 125
            self.sound_threat = ([me["pos"][0] + d * math.cos(s["bearing"]),
                                  me["pos"][1] + d * math.sin(s["bearing"])], t)

    def _pick_upgrade(self, obs, action):
        offer = obs.get("offer")
        if offer and offer.get("choices"):
            choices = offer["choices"]
            index = max(range(len(choices)),
                        key=lambda i: UPGRADE_PRIORITY.get(choices[i]["id"], 50))
            action["pick"] = index

    def _take_loot(self, obs, action):
        me = obs["self"]
        second = me["weapons"][1] if len(me["weapons"]) > 1 else None
        own_rank = WEAPON_RANK.get(second["kind"], -1) if second else -1
        best = None
        for p in obs.get("pickups", []):
            rank = WEAPON_RANK.get(p["kind"], -1)
            if rank <= own_rank or p["kind"] == "gun":
                continue
            d = distance2(me["pos"], p["pos"])
            if d <= 4.2 and abs(me["pos"][2] - p["pos"][2]) <= 4.2:
                if best is None or rank > WEAPON_RANK[best["kind"]]:
                    best = p
        if best:
            action["take"] = best["id"]
            if second:
                action["drop"] = 1

    def _safe_point(self, obs):
        zone = obs["zone"]
        t = obs["t"]
        center = zone["next_center"]
        radius = zone["next_radius"]
        key = (tuple(center), radius)
        if self.safe_goal is not None and key == self.safe_zone_key:
            return self.safe_goal
        if radius > 100:
            # Do not crowd the centre with every other surviving mech.
            r = min(radius * 0.52, 175)
        else:
            r = radius * 0.32
        angle = self.phase + self.slot * 0.71
        desired = [center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)]
        # Prefer a routeable free cell; cover-seeking is handled while evading.
        node = self.arena.nearest_free(*desired)
        self.safe_goal = list(self.arena._grid_point(node)) if node else list(center)
        self.safe_zone_key = key
        return self.safe_goal

    def _threats(self, obs):
        t = obs["t"]
        threats = [(v[0], 1.0 if t - v[1] < 0.2 else 0.45)
                   for v in self.threat_memory.values()]
        if self.sound_threat and t - self.sound_threat[1] < 2.0:
            threats.append((self.sound_threat[0], 0.35))
        return threats

    def _escape_goal(self, obs, threats):
        me = obs["self"]
        p = me["pos"]
        zone = obs["zone"]
        t = obs["t"]
        # After the next shrink begins, staying in the next circle matters.
        use_next = t >= zone["shrink_start"] - 8
        center = zone["next_center"] if use_next else zone["center"]
        radius = zone["next_radius"] if use_next else zone["radius"]
        usable_radius = max(0.0, radius - 8)
        current = self.safe_goal or center
        candidates = []
        for k in range(16):
            a = k * math.tau / 16
            for reach in (55.0, 95.0):
                raw = [p[0] + reach * math.cos(a), p[1] + reach * math.sin(a)]
                q = clamp_to_circle(raw, center, usable_radius)
                if not self.arena.walkable(p, q):
                    continue
                threat_score = 0.0
                qz = self.arena.height(q[0], q[1]) + 7.0
                for enemy, weight in threats:
                    d = distance2(q, enemy)
                    # Distance and changing our bearing both make gunfire harder.
                    threat_score += weight * (260.0 / max(30.0, d)) ** 2
                    # A nearby building is better than an open-field sprint:
                    # blocked fire permits the five-second repair timer to run.
                    enemy_z = enemy[2] + 4.5 if len(enemy) > 2 else p[2] + 4.5
                    if not self.arena.clear_shot([q[0], q[1], qz], [enemy[0], enemy[1], enemy_z]):
                        threat_score -= 3.0 * weight
                zone_dist = distance2(q, center)
                if zone_dist > usable_radius:
                    threat_score += 100
                # A short route is safer than crossing the whole circle.
                score = threat_score + 0.002 * distance2(q, current)
                candidates.append((score, q))
        if candidates:
            return min(candidates, key=lambda item: item[0])[1]
        # No direct escape ray: A* can take us around the obstructing building.
        vx = vy = 0.0
        for enemy, weight in threats:
            dx, dy = p[0] - enemy[0], p[1] - enemy[1]
            d2 = max(100.0, dx * dx + dy * dy)
            vx += weight * dx / d2
            vy += weight * dy / d2
        ux, uy = unit(vx, vy)
        return clamp_to_circle([p[0] + ux * 80, p[1] + uy * 80], center, usable_radius)

    def _combat_goal(self, obs, target, threats):
        me = obs["self"]
        p, e = me["pos"], target["pos"]
        d = distance2(p, e)
        if obs["t"] - self.last_strafe_change > 2.2:
            self.strafe *= -1
            self.last_strafe_change = obs["t"]
        ux, uy = unit(p[0] - e[0], p[1] - e[1])
        # Keep gun range, orbit rather than backpedal in a predictable line.
        radial = 35 if d < 80 else (-25 if d > 165 else 0)
        vx = ux * radial + (-uy) * self.strafe * 48
        vy = uy * radial + ux * self.strafe * 48
        q = [p[0] + vx, p[1] + vy]
        zone = obs["zone"]
        use_next = obs["t"] >= zone["shrink_start"]
        center = zone["next_center"] if use_next else zone["center"]
        radius = zone["next_radius"] if use_next else zone["radius"]
        q = clamp_to_circle(q, center, max(0, radius - 5))
        if self.arena.walkable(p, q):
            return q
        return self._escape_goal(obs, threats)

    def _loot_goal(self, obs):
        me = obs["self"]
        p = me["pos"]
        second = me["weapons"][1] if len(me["weapons"]) > 1 else None
        rank = WEAPON_RANK.get(second["kind"], -1) if second else -1
        candidates = []
        for kind, pos, seen_t in self.loot.values():
            if WEAPON_RANK.get(kind, -1) > rank:
                d = distance2(p, pos)
                height_delta = pos[2] - p[2]
                ground = self.arena.height(pos[0], pos[1])
                # Do not attempt a ground route to a rooftop pickup.
                if pos[2] > ground + 3.0 and height_delta > 4.0:
                    continue
                if 5 < d < 115 and height_delta < 5.0:
                    candidates.append((d - WEAPON_RANK[kind] * 12, pos, "weapon"))
        if second is not None and obs["t"] > 20:
            for pos, seen_t in self.cubes.values():
                d = distance2(p, pos)
                if 2 < d < 65:
                    candidates.append((d + 18, pos, "cube"))
        if not candidates:
            return None
        _, pos, kind = min(candidates, key=lambda c: c[0])
        return pos, kind

    def _drop_goal(self, obs):
        if self.threat_memory or obs["self"]["hp"] < obs["self"]["max_hp"] * 0.7:
            return None
        p = obs["self"]["pos"]
        valid = []
        for d in obs.get("drops", []):
            if d.get("lands_in", 1) <= 5 and distance2(p, d["pos"]) < 65:
                valid.append(d)
        if valid:
            d = min(valid, key=lambda d: distance2(p, d["pos"]))
            return d["pos"], d
        return None

    def _navigate(self, obs, goal, force=False):
        me = obs["self"]
        p = me["pos"]
        t = obs["t"]
        goal = [goal[0], goal[1]]
        if (force or self.route_goal is None or distance2(goal, self.route_goal) > 18
                or (not self.route and distance2(p, goal) > 7 and t - self.last_route_t > 1.0)):
            self.route = self.arena.route(p, goal)
            self.route_goal = goal
            self.last_route_t = t
        while self.route and distance2(p, self.route[0]) < 5.0:
            self.route.pop(0)
        waypoint = self.route[0] if self.route else goal
        dx, dy = waypoint[0] - p[0], waypoint[1] - p[1]
        d = math.hypot(dx, dy)
        if d < 2.0 and distance2(p, goal) < 4.0:
            return [0.0, 0.0]
        ux, uy = unit(dx, dy)
        # Slow near the final waypoint to avoid noisy orbit around loot.
        magnitude = min(1.0, max(0.35, d / 9.0))
        return [ux * magnitude, uy * magnitude]

    def _dodge(self, obs, move):
        me = obs["self"]
        p = me["pos"]
        for bullet in obs.get("projectiles", []):
            v = bullet["vel"]
            speed2 = v[0] ** 2 + v[1] ** 2 + v[2] ** 2
            if speed2 < 1:
                continue
            rel = [p[i] - bullet["pos"][i] for i in range(3)]
            impact = sum(rel[i] * v[i] for i in range(3)) / speed2
            if not 0.02 < impact < 0.65:
                continue
            closest = math.sqrt(max(0.0, sum((rel[i] - v[i] * impact) ** 2 for i in range(3))))
            if closest < 8.0:
                ux, uy = unit(-v[1] * self.strafe, v[0] * self.strafe)
                self.last_dodge_t = obs["t"]
                return [ux, uy]
        return move

    def act(self, obs):
        self._remember(obs)
        me = obs["self"]
        t = obs["t"]
        p = me["pos"]
        zone = obs["zone"]
        action = {"tick": obs["tick"]}
        self._pick_upgrade(obs, action)
        self._take_loot(obs, action)

        visible_mechs = [m for m in obs["mechs"] if m["kind"] == "mech"]
        nearest = min(visible_mechs, key=lambda m: distance2(p, m["pos"]), default=None)
        nearest_d = distance2(p, nearest["pos"]) if nearest else 1000.0
        hp_frac = me["hp"] / max(1.0, me["max_hp"])
        threats = self._threats(obs)
        recent_damage = t - self.last_damage_t
        attacker_ids = {e.get("by") for e in obs["events"]
                        if e["type"] == "damaged" and e.get("by") is not None}
        if visible_mechs:
            nearest = min(visible_mechs, key=lambda m: (
                distance2(p, m["pos"])
                + 70 * m.get("hp", 1400) / max(1.0, m.get("max_hp", 1400))
                - (500 if m["id"] in attacker_ids else 0)))
            nearest_d = distance2(p, nearest["pos"])

        late = zone["next_radius"] <= 70 or zone["radius"] <= 75
        # Retreat is a response to real danger, not to every incoming bullet.
        # In v2 ordinary hits continuously refreshed ceasefire, letting a single
        # pursuer deal damage without receiving any in return.
        close_enemies = sum(distance2(p, m["pos"]) < 130 for m in visible_mechs)
        critical = hp_frac < 0.30 and nearest_d < 140
        outnumbered = close_enemies >= 2
        if critical:
            self.retreat_until = max(self.retreat_until, t + 2.0)
        elif outnumbered and recent_damage < 1.0:
            self.retreat_until = max(self.retreat_until, t + 1.5)
        recovering = hp_frac < 0.90 and t < self.retreat_until
        # At close range or late in the match there is no useful running room.
        retreating = (recovering or outnumbered) and nearest_d >= 65 and not late
        if self.retreat_until < t - 8:
            self.retreat_until = -100.0

        # Opportunistic supply repair only when uncontested and very close.
        drop = self._drop_goal(obs)
        use_next = t >= zone["shrink_start"] - 8
        safe_center = zone["next_center"] if use_next else zone["center"]
        safe_radius = zone["next_radius"] if use_next else zone["radius"]
        outside_safe = distance2(p, safe_center) > max(0.0, safe_radius - 12)
        travel_s = max(0.0, distance2(p, safe_center) - safe_radius) / max(1.0, me["stats"]["walk_speed"])
        # Route to an edge rather than pointlessly driving to a distant centre.
        if outside_safe or not me["in_zone"]:
            ux, uy = unit(p[0] - safe_center[0], p[1] - safe_center[1])
            edge = [safe_center[0] + ux * max(0.0, safe_radius * 0.72),
                    safe_center[1] + uy * max(0.0, safe_radius * 0.72)]
            node = self.arena.nearest_free(*edge)
            zone_goal = list(self.arena._grid_point(node)) if node else list(safe_center)
        else:
            zone_goal = self._safe_point(obs)
        must_rotate = outside_safe or not me["in_zone"] or t + travel_s + 12 >= zone["shrink_end"]
        loot = self._loot_goal(obs)
        if retreating and threats:
            goal, self.goal_kind = self._escape_goal(obs, threats), "retreat"
        elif outside_safe or not me["in_zone"] or must_rotate:
            goal, self.goal_kind = zone_goal, "zone"
        elif nearest and (nearest_d < (195 if late else 145) or recent_damage < 3.5
                           or (nearest_d < 180 and self.retreat_until < t)):
            goal, self.goal_kind = self._combat_goal(obs, nearest, threats), "fight"
        elif drop:
            goal, self.goal_kind = drop[0], "drop"
            if distance2(p, goal) < drop[1].get("radius", 8) * 0.55 and drop[1].get("lands_in", 1) <= 0:
                action["move"] = [0.0, 0.0]
        elif loot:
            goal, self.goal_kind = loot[0], loot[1]
        elif late or zone["radius"] < 220:
            goal, self.goal_kind = self._safe_point(obs), "zone"
        else:
            # Hold the nearest safe position; walking aimlessly is loud and
            # invites the coordinated practice bots to focus us.
            goal, self.goal_kind = p, "hold"
            action["move"] = [0.0, 0.0]

        if "move" not in action:
            action["move"] = self._navigate(obs, goal)
        action["move"] = self._dodge(obs, action["move"])

        # Detect an obstructed route and use a short jump/jet rather than remain
        # stuck forever.  A fresh route is requested on the following decision.
        speed = math.hypot(me["vel"][0], me["vel"][1])
        moving = math.hypot(*action["move"]) > 0.5
        if moving and speed < 0.8 and me.get("grounded"):
            if self.stuck_since is None:
                self.stuck_since = t
            if t - self.stuck_since > 0.8:
                self.stuck_until = t + 0.65
                self.stuck_since = None
                self.route_goal = None
        else:
            self.stuck_since = None
        unsticking = t < self.stuck_until
        action["jump"] = unsticking and me.get("grounded", False)
        urgent = not me["in_zone"] or self.goal_kind == "retreat" or t - self.last_dodge_t < 0.15
        if self.boosting and me["energy"] < 25:
            self.boosting = False
        elif not self.boosting and me["energy"] > 60 and urgent:
            self.boosting = True
        action["boost"] = bool(me["grounded"] and moving and
                               ((self.boosting and urgent) or unsticking))

        # Keep pressure on an isolated visible target.  Only a genuine retreat
        # with broken contact justifies a ceasefire for regeneration.
        target = nearest
        if target is None and not self.threat_memory and recent_damage > 5:
            npcs = [m for m in obs["mechs"] if m["kind"] == "npc" and distance2(p, m["pos"]) < 28]
            target = npcs[0] if npcs else None
        clear = False
        if target:
            d = distance2(p, target["pos"])
            muzzle = me["stats"].get("muzzle_height", 7)
            origin = [p[0], p[1], p[2] + muzzle]
            center = [target["pos"][0], target["pos"][1], target["pos"][2] + 4.0]
            engage_range = 205 if late or recent_damage < 5 else 155
            if target["kind"] == "npc":
                engage_range = 28
            if recovering and recent_damage > 1.0:
                # Continue firing if the pursuer still has a clear shot at us.
                # Ceasefire only pays when cover actually protects us.
                attacker_los = self.arena.clear_shot(center, origin)
                engage_range = 180 if attacker_los else 0
            elif recent_damage < 3.5 or d < 120:
                engage_range = max(engage_range, 190)
            clear = d <= engage_range and self.arena.clear_shot(origin, center)
        combat = self.weapons.act(obs, target, clear)
        action.update(combat)
        if target is None:
            if recent_damage < 2:
                for e in reversed(obs["events"]):
                    if e["type"] == "damaged" and e.get("bearing") is not None:
                        action["aim"] = [e["bearing"], 0.0]
                        break
                else:
                    action["aim"] = [self.phase + t * 0.9, -0.03]
            else:
                action["aim"] = [self.phase + t * 0.9, -0.03]
            # Never hold a laser charge while simply scanning.
            if len(me["weapons"]) > 1 and me["weapons"][1] and me["weapons"][1]["kind"] == "laser":
                if me["weapons"][1].get("charge", 0) > 0:
                    action["fire"] = [False, False]
        return action
