"""Target selection and aiming for the mechfight protocol.

The controller deliberately uses only observations and the hello config.  In
particular, ``clear_shot`` is supplied by the caller because this module does
not need (or attempt) map/line-of-sight access.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Optional, Sequence

_EPS = 1.0e-6


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _point3(value: Any) -> Optional[tuple[float, float, float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 3:
        return None
    return (_number(value[0]), _number(value[1]), _number(value[2]))


def _velocity(actor: Mapping[str, Any]) -> tuple[float, float, float]:
    return _point3(actor.get("vel")) or (0.0, 0.0, 0.0)


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def wrap_angle(angle: float) -> float:
    """Return an angle in [-pi, pi]."""
    return (float(angle) + math.pi) % (2.0 * math.pi) - math.pi


def aim_at(muzzle: Sequence[float], point: Sequence[float]) -> list[float]:
    """Desired yaw/pitch from a muzzle to a world-space point."""
    dx = float(point[0]) - float(muzzle[0])
    dy = float(point[1]) - float(muzzle[1])
    dz = float(point[2]) - float(muzzle[2])
    return [math.atan2(dy, dx), math.atan2(dz, math.hypot(dx, dy))]


def aim_errors(actual: Any, desired: Sequence[float]) -> Optional[tuple[float, float]]:
    """Absolute yaw/pitch errors from the mech's actual, slewed aim."""
    if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes)) or len(actual) < 2:
        return None
    return (
        abs(wrap_angle(_number(actual[0]) - float(desired[0]))),
        abs(_number(actual[1]) - float(desired[1])),
    )


def aim_tolerance(distance: float, radius: float, height: float) -> tuple[float, float]:
    """Conservative angular gate, widened by the target's apparent size."""
    d = max(1.0, float(distance))
    yaw = min(0.16, max(0.012, math.atan2(max(0.1, radius * 0.65), d)))
    pitch = min(0.12, max(0.012, math.atan2(max(0.1, height * 0.25), d)))
    return yaw, pitch


def is_aligned(actual: Any, desired: Sequence[float], distance: float,
               radius: float, height: float) -> bool:
    errors = aim_errors(actual, desired)
    if errors is None:
        return False
    yaw_tol, pitch_tol = aim_tolerance(distance, radius, height)
    return errors[0] <= yaw_tol and errors[1] <= pitch_tol


def target_center(actor: Mapping[str, Any], config: Mapping[str, Any]) -> Optional[list[float]]:
    """Center of a mech/NPC, including mech cube scaling when present."""
    pos = _point3(actor.get("pos"))
    if pos is None:
        return None
    cubes_cfg = config.get("cubes", {})
    if actor.get("kind") == "npc":
        height = _number(config.get("npc", {}).get("height"), 3.5)
    else:
        mech_cfg = config.get("mech", {})
        size_per_cube = _number(cubes_cfg.get("size_per_cube"), 0.05)
        scale = 1.0 + size_per_cube * max(0.0, _number(actor.get("cubes"), 0.0))
        height = _number(mech_cfg.get("height"), 9.0) * scale
    return [pos[0], pos[1], pos[2] + 0.5 * max(0.0, height)]


def target_radius(actor: Mapping[str, Any], config: Mapping[str, Any]) -> float:
    if actor.get("kind") == "npc":
        return max(0.1, _number(config.get("npc", {}).get("radius"), 1.8))
    mech_cfg = config.get("mech", {})
    scale = 1.0 + _number(config.get("cubes", {}).get("size_per_cube"), 0.05) * max(
        0.0, _number(actor.get("cubes"), 0.0))
    return max(0.1, _number(mech_cfg.get("radius"), 2.5) * scale)


def target_height(actor: Mapping[str, Any], config: Mapping[str, Any]) -> float:
    if actor.get("kind") == "npc":
        return max(0.1, _number(config.get("npc", {}).get("height"), 3.5))
    scale = 1.0 + _number(config.get("cubes", {}).get("size_per_cube"), 0.05) * max(
        0.0, _number(actor.get("cubes"), 0.0))
    return max(0.1, _number(config.get("mech", {}).get("height"), 9.0) * scale)


def predict_gun_lead(muzzle: Sequence[float], center: Sequence[float],
                     velocity: Sequence[float], speed: float,
                     iterations: int = 5) -> tuple[list[float], float, float]:
    """Fixed-point projectile interception: point, shot distance, flight time.

    Recomputing time from each newly predicted position converges quickly for
    normal mech velocities and handles vertical as well as horizontal motion.
    """
    point = [float(center[0]), float(center[1]), float(center[2])]
    speed = max(0.0, float(speed))
    flight_time = 0.0
    for _ in range(max(1, int(iterations))):
        distance = _distance(muzzle, point)
        flight_time = distance / speed if speed > _EPS else 0.0
        updated = [float(center[i]) + float(velocity[i]) * flight_time for i in range(3)]
        change = _distance(point, updated)
        point = updated
        if change < 1.0e-4:
            break
    return point, _distance(muzzle, point), flight_time


def mortar_solution(muzzle: Sequence[float], point: Sequence[float], speed: float,
                    gravity: float, high_arc: bool = False
                    ) -> Optional[tuple[float, float, float]]:
    """Ballistic (yaw, pitch, flight_time), or None if the point is unreachable."""
    speed = float(speed)
    gravity = float(gravity)
    if speed <= _EPS or gravity <= _EPS:
        return None
    dx = float(point[0]) - float(muzzle[0])
    dy = float(point[1]) - float(muzzle[1])
    dz = float(point[2]) - float(muzzle[2])
    horizontal = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    if horizontal < _EPS:
        # Such a shot is normally rejected by self-splash anyway.
        pitch = math.pi / 2.0 if dz >= 0.0 else -math.pi / 2.0
        vertical_speed = math.copysign(speed, dz)
        discriminant = vertical_speed * vertical_speed - 2.0 * gravity * dz
        if discriminant < 0.0:
            return None
        flight_time = (vertical_speed + math.sqrt(discriminant)) / gravity
        return (yaw, pitch, flight_time) if flight_time > 0.0 else None
    v2 = speed * speed
    discriminant = v2 * v2 - gravity * (gravity * horizontal * horizontal + 2.0 * dz * v2)
    if discriminant < -_EPS:
        return None
    root = math.sqrt(max(0.0, discriminant))
    numerator = v2 + root if high_arc else v2 - root
    pitch = math.atan2(numerator, gravity * horizontal)
    horizontal_speed = speed * math.cos(pitch)
    if horizontal_speed <= _EPS:
        return None
    flight_time = horizontal / horizontal_speed
    if not math.isfinite(flight_time) or flight_time <= 0.0:
        return None
    return yaw, pitch, flight_time


def mortar_self_safe(self_center: Sequence[float], impact: Sequence[float],
                     self_radius: float, splash_radius: float,
                     margin: float = 0.5) -> bool:
    """Reject shots whose predicted blast can reach our own cylinder."""
    safe_distance = max(0.0, float(splash_radius)) + max(0.0, float(self_radius)) + max(0.0, margin)
    return _distance(self_center, impact) > safe_distance


def lightning_in_cone(actual: Any, desired: Sequence[float], distance: float,
                      range_m: float, cone_deg: float) -> bool:
    """Lightning uses actual yaw, range, and its configured yaw cone."""
    errors = aim_errors(actual, desired)
    return bool(errors is not None and distance <= max(0.0, range_m) + _EPS
                and errors[0] <= math.radians(max(0.0, cone_deg)) + _EPS)


class WeaponController:
    """Choose a visible opponent and produce the combat fields of an action.

    ``visible_fn``, when supplied to :meth:`choose_target`, is called with each
    actor dictionary.  Mechs always exclude NPCs from consideration; NPCs are
    considered only if no mech candidate remains and the NPC is close.
    """

    def __init__(self, config: Mapping[str, Any]):
        self.config = config if isinstance(config, Mapping) else {}
        self._laser_held = [False, False]
        self._laser_release_pending = [False, False]
        self._decision_dt = _number(self.config.get("match", {}).get("decide_every"), 2.0) / max(
            1.0, _number(self.config.get("match", {}).get("tick_hz"), 20.0))

    def _stat(self, weapon: Mapping[str, Any], name: str, default: float = 0.0) -> float:
        kind = weapon.get("kind")
        stats = weapon.get("stats", {})
        if isinstance(stats, Mapping) and name in stats:
            return _number(stats.get(name), default)
        configured = self.config.get("weapons", {}).get(kind, {})
        return _number(configured.get(name), default)

    def _muzzle(self, me: Mapping[str, Any], mortar: bool = False) -> Optional[list[float]]:
        pos = _point3(me.get("pos"))
        if pos is None:
            return None
        stats = me.get("stats", {})
        if not isinstance(stats, Mapping):
            stats = {}
        mech_cfg = self.config.get("mech", {})
        scale = 1.0 + _number(self.config.get("cubes", {}).get("size_per_cube"), 0.05) * max(
            0.0, _number(me.get("cubes"), 0.0))
        if mortar:
            if "mortar_height" in stats:
                height = _number(stats.get("mortar_height"), 9.5)
            else:
                body_height = _number(stats.get("height"), _number(mech_cfg.get("height"), 9.0) * scale)
                height = body_height + 0.5 * scale
        else:
            height = _number(stats.get("muzzle_height"),
                             _number(mech_cfg.get("muzzle_height"), 7.0) * scale)
        return [pos[0], pos[1], pos[2] + height]

    def _self_center(self, me: Mapping[str, Any]) -> Optional[list[float]]:
        pos = _point3(me.get("pos"))
        if pos is None:
            return None
        stats = me.get("stats", {})
        if not isinstance(stats, Mapping):
            stats = {}
        scale = 1.0 + _number(self.config.get("cubes", {}).get("size_per_cube"), 0.05) * max(
            0.0, _number(me.get("cubes"), 0.0))
        height = _number(stats.get("height"), _number(self.config.get("mech", {}).get("height"), 9.0) * scale)
        return [pos[0], pos[1], pos[2] + 0.5 * height]

    def _pitch_limits(self, me: Mapping[str, Any]) -> tuple[float, float]:
        stats = me.get("stats", {})
        if not isinstance(stats, Mapping):
            stats = {}
        cfg = self.config.get("mech", {})
        low = _number(stats.get("min_pitch"), _number(cfg.get("min_pitch"), -0.7))
        high = _number(stats.get("max_pitch"), _number(cfg.get("max_pitch"), 1.3))
        return (min(low, high), max(low, high))

    def _clamped_aim(self, me: Mapping[str, Any], desired: Sequence[float]) -> list[float]:
        low, high = self._pitch_limits(me)
        return [wrap_angle(desired[0]), min(high, max(low, _number(desired[1])))]

    def _pitch_reachable(self, me: Mapping[str, Any], desired: Sequence[float]) -> bool:
        low, high = self._pitch_limits(me)
        return low - _EPS <= desired[1] <= high + _EPS

    def choose_target(self, obs: Mapping[str, Any],
                      visible_fn: Optional[Callable[[Mapping[str, Any]], bool]] = None
                      ) -> Optional[Mapping[str, Any]]:
        me = obs.get("self", {})
        self_pos = _point3(me.get("pos")) if isinstance(me, Mapping) else None
        if self_pos is None:
            return None
        self_id = me.get("id")
        attacker_ids = set()
        events = obs.get("events", [])
        for event in events if isinstance(events, Sequence) and not isinstance(events, (str, bytes)) else []:
            if isinstance(event, Mapping) and event.get("type") == "damaged" and event.get("by") is not None:
                attacker_ids.add(event.get("by"))
        beams = obs.get("beams", [])
        for beam in beams if isinstance(beams, Sequence) and not isinstance(beams, (str, bytes)) else []:
            if isinstance(beam, Mapping) and beam.get("by") is not None:
                attacker_ids.add(beam.get("by"))

        mechs = []
        npcs = []
        actors = obs.get("mechs", []) or []
        for actor in actors:
            if not isinstance(actor, Mapping) or actor.get("id") == self_id:
                continue
            kind = actor.get("kind")
            if kind not in ("mech", "npc") or _point3(actor.get("pos")) is None:
                continue
            if _number(actor.get("hp"), 1.0) <= 0.0:
                continue
            if visible_fn is not None and not visible_fn(actor):
                continue
            if kind == "mech":
                mechs.append(actor)
            else:
                npcs.append(actor)

        def score(actor: Mapping[str, Any]) -> tuple[float, float, float]:
            pos = _point3(actor.get("pos"))
            assert pos is not None  # filtered above
            distance = _distance(self_pos, pos)
            hp_group = self.config.get("npc", {}) if actor.get("kind") == "npc" else self.config.get("mech", {})
            max_hp = max(1.0, _number(actor.get("max_hp"), _number(hp_group.get("hp"), 350.0 if actor.get("kind") == "npc" else 1400.0)))
            hp_fraction = min(1.0, max(0.0, _number(actor.get("hp"), max_hp) / max_hp))
            attacking = actor.get("id") in attacker_ids or bool(actor.get("charging"))
            # Recent attackers and charging lasers take priority.  Otherwise
            # distance dominates, with a substantial finish-off/low-HP bonus.
            value = distance + 80.0 * hp_fraction - (500.0 if attacking else 0.0)
            if _number(actor.get("hp"), max_hp) <= 100.0:
                value -= 30.0
            actor_aim = actor.get("aim")
            if isinstance(actor_aim, Sequence) and len(actor_aim) >= 2 and distance > _EPS:
                toward_me = math.atan2(self_pos[1] - pos[1], self_pos[0] - pos[0])
                if abs(wrap_angle(_number(actor_aim[0]) - toward_me)) < math.radians(35.0):
                    value -= 15.0
            return value, distance, _number(actor.get("id"), 0.0)

        if mechs:
            return min(mechs, key=score)
        npc_range = _number(self.config.get("npc", {}).get("aggro_range"), 45.0)
        close_npcs = [a for a in npcs if _distance(self_pos, _point3(a.get("pos")) or self_pos) <= npc_range]
        return min(close_npcs, key=score) if close_npcs else None

    def _candidate(self, me: Mapping[str, Any], weapon: Mapping[str, Any],
                   center: Sequence[float], velocity: Sequence[float],
                   radius: float, height: float) -> Optional[dict[str, Any]]:
        kind = weapon.get("kind")
        muzzle = self._muzzle(me, mortar=kind == "mortar")
        if muzzle is None:
            return None
        point = list(center)
        solution = None
        if kind == "gun":
            point, shot_distance, flight_time = predict_gun_lead(
                muzzle, center, velocity, self._stat(weapon, "speed", 252.0))
            desired = aim_at(muzzle, point)
            range_ok = shot_distance <= self._stat(weapon, "range", 230.0) + _EPS
        elif kind == "mortar":
            speed = self._stat(weapon, "speed", 72.0)
            gravity = self._stat(weapon, "gravity", 22.0)
            # Intercept with the ballistic flight time, not gun flight time.
            for _ in range(4):
                solution = mortar_solution(muzzle, point, speed, gravity)
                if solution is None:
                    break
                point = [center[i] + velocity[i] * solution[2] for i in range(3)]
            solution = mortar_solution(muzzle, point, speed, gravity)
            if solution is None:
                desired = aim_at(muzzle, point)
                shot_distance = _distance(muzzle, point)
                range_ok = False
            else:
                desired = [solution[0], solution[1]]
                shot_distance = _distance(muzzle, point)
                configured_range = self._stat(weapon, "range", float("inf"))
                ttl = self._stat(weapon, "ttl", 7.0)
                range_ok = solution[2] <= ttl + _EPS and shot_distance <= configured_range + _EPS
        else:
            desired = aim_at(muzzle, point)
            shot_distance = _distance(muzzle, point)
            default_range = 280.0 if kind == "laser" else 45.0
            range_ok = shot_distance <= self._stat(weapon, "range", default_range) + _EPS
        range_ok = range_ok and self._pitch_reachable(me, desired)
        return {
            "muzzle": muzzle,
            "point": point,
            "desired": desired,
            "distance": shot_distance,
            "range_ok": range_ok,
            "solution": solution,
            "aligned": is_aligned(me.get("aim"), desired, shot_distance, radius, height),
            "self_safe": True,
        }

    def _release_laser(self, slot: int, charge: float) -> None:
        self._laser_held[slot] = False
        if charge > _EPS:
            self._laser_release_pending[slot] = True

    def _empty_action(self, me: Mapping[str, Any], weapons: Sequence[Any], reload: bool) -> dict[str, Any]:
        actual = me.get("aim")
        if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)) and len(actual) >= 2:
            aim = self._clamped_aim(me, [_number(actual[0]), _number(actual[1])])
        else:
            aim = [0.0, 0.0]
        for slot in range(2):
            weapon = weapons[slot] if slot < len(weapons) else None
            if isinstance(weapon, Mapping) and weapon.get("kind") == "laser":
                charge = max(0.0, _number(weapon.get("charge"), 0.0))
                self._release_laser(slot, charge)
                if charge <= _EPS:
                    self._laser_release_pending[slot] = False
            else:
                self._laser_held[slot] = False
                self._laser_release_pending[slot] = False
        return {"aim": aim, "fire": [False, False], "reload": reload}

    def act(self, obs: Mapping[str, Any], target: Optional[Mapping[str, Any]],
            clear_shot: bool) -> dict[str, Any]:
        """Return ``aim``, two trigger states, and gun reload (no tick/move)."""
        me = obs.get("self", {})
        if not isinstance(me, Mapping):
            me = {}
        raw_weapons = me.get("weapons", [])
        weapons = raw_weapons if isinstance(raw_weapons, Sequence) and not isinstance(raw_weapons, (str, bytes)) else []
        held = [weapons[i] if i < len(weapons) and isinstance(weapons[i], Mapping) else None
                for i in range(2)]
        reload = False
        for weapon in held:
            if weapon is not None and weapon.get("kind") == "gun":
                ammo = _number(weapon.get("ammo"), self._stat(weapon, "mag", 12.0))
                reloading = _number(weapon.get("reload"), 0.0)
                if ammo <= _EPS and reloading <= _EPS and self._stat(weapon, "reload", 2.4) > 0.0:
                    reload = True

        center = target_center(target, self.config) if isinstance(target, Mapping) else None
        if center is None:
            return self._empty_action(me, weapons, reload)

        radius = target_radius(target, self.config)
        height = target_height(target, self.config)
        velocity = _velocity(target)
        candidates: dict[int, dict[str, Any]] = {}
        for slot, weapon in enumerate(held):
            if weapon is None or weapon.get("kind") not in ("gun", "mortar", "laser", "lightning"):
                continue
            candidate = self._candidate(me, weapon, center, velocity, radius, height)
            if candidate is None:
                continue
            candidate["shot_range_ok"] = candidate["range_ok"]
            if weapon.get("kind") == "mortar":
                own_center = self._self_center(me)
                own_radius = target_radius({"kind": "mech", "cubes": me.get("cubes", 0.0)}, self.config)
                candidate["self_safe"] = bool(own_center is not None and mortar_self_safe(
                    own_center, candidate["point"], own_radius,
                    self._stat(weapon, "splash_radius", 7.0)))
            candidates[slot] = candidate

        if not candidates:
            muzzle = self._muzzle(me)
            desired = aim_at(muzzle, center) if muzzle is not None else me.get("aim", [0.0, 0.0])
            action = self._empty_action(me, weapons, reload)
            action["aim"] = self._clamped_aim(me, desired)
            return action

        def ready(slot: int) -> bool:
            weapon = held[slot]
            return bool(weapon is not None and _number(weapon.get("cooldown"), 0.0) <= _EPS)

        def gun_available(slot: int) -> bool:
            weapon = held[slot]
            return bool(weapon is not None and weapon.get("kind") == "gun"
                        and _number(weapon.get("ammo"), self._stat(weapon, "mag", 12.0)) > _EPS
                        and _number(weapon.get("reload"), 0.0) <= _EPS)

        # Never start charging a laser while intentionally holding fire.  The
        # caller may still want to face the threat for rear-armor protection.
        if not clear_shot:
            desired = next(iter(candidates.values()))["desired"]
            for slot, weapon in enumerate(held):
                if weapon is not None and weapon.get("kind") == "laser":
                    charge = max(0.0, _number(weapon.get("charge"), 0.0))
                    self._release_laser(slot, charge)
            return {"aim": self._clamped_aim(me, desired),
                    "fire": [False, False], "reload": reload}

        # Charging lasers own the torso so their release uses the same aim.
        primary = next((s for s, w in enumerate(held) if w is not None and w.get("kind") == "laser"
                        and s in candidates and (_number(w.get("charge"), 0.0) > _EPS
                                                or self._laser_held[s])), None)
        if primary is None:
            # Use a ready situational special; fall back to the arm gun while
            # it cools down, charges, or cannot safely reach the target.
            for kind in ("lightning", "laser", "mortar"):
                for slot, weapon in enumerate(held):
                    if slot not in candidates or weapon is None or weapon.get("kind") != kind or not ready(slot):
                        continue
                    candidate = candidates[slot]
                    if not candidate["range_ok"]:
                        continue
                    if kind == "lightning" and _number(me.get("energy"), 0.0) + _EPS < self._stat(weapon, "energy", 3.0):
                        continue
                    if kind == "mortar" and not candidate["self_safe"]:
                        continue
                    primary = slot
                    break
                if primary is not None:
                    break
        if primary is None:
            primary = next((s for s, w in enumerate(held) if s in candidates and w is not None
                            and w.get("kind") == "gun" and gun_available(s)
                            and candidates[s]["range_ok"]), None)
        if primary is None:
            # An out-of-range laser must not keep recharging and releasing at
            # zero charge while a gun (or another special) could be prepared.
            primary = next((s for s, w in enumerate(held) if s in candidates and w is not None
                            and w.get("kind") != "laser" and ready(s)), None)
        if primary is None:
            primary = next(iter(candidates))

        fire = [False, False]
        for slot, weapon in enumerate(held):
            if weapon is None:
                self._laser_held[slot] = False
                self._laser_release_pending[slot] = False
                continue
            kind = weapon.get("kind")
            if kind != "laser":
                self._laser_held[slot] = False
                self._laser_release_pending[slot] = False
            candidate = candidates.get(slot)
            charge = max(0.0, _number(weapon.get("charge"), 0.0))
            if kind == "laser" and charge <= _EPS:
                self._laser_release_pending[slot] = False
                self._laser_held[slot] = False
            if not clear_shot or candidate is None:
                if kind == "laser":
                    self._release_laser(slot, charge)
                continue
            cooldown = _number(weapon.get("cooldown"), 0.0)
            if kind == "gun":
                if (cooldown <= _EPS and candidate["range_ok"] and candidate["aligned"]
                        and gun_available(slot)):
                    fire[slot] = True
            elif kind == "lightning":
                enough_energy = _number(me.get("energy"), 0.0) + _EPS >= self._stat(weapon, "energy", 3.0)
                if (cooldown <= _EPS and enough_energy and candidate["range_ok"]
                        and lightning_in_cone(me.get("aim"), candidate["desired"], candidate["distance"],
                                              self._stat(weapon, "range", 45.0),
                                              self._stat(weapon, "cone_deg", 30.0))):
                    fire[slot] = True
            elif kind == "mortar":
                if (cooldown <= _EPS and candidate["range_ok"] and candidate["aligned"]
                        and candidate["self_safe"] and candidate["solution"] is not None):
                    fire[slot] = True
            elif kind == "laser":
                if self._laser_release_pending[slot] and charge > _EPS:
                    continue
                if not candidate["range_ok"]:
                    self._release_laser(slot, charge)
                    # Pitch-clamped aim should never cause an endless
                    # zero-charge hold/release cycle.  Horizontal out-of-range
                    # shots still begin charging while the mech closes in.
                    if not candidate["shot_range_ok"]:
                        continue
                    if cooldown <= _EPS:
                        self._laser_held[slot] = True
                        fire[slot] = True
                    continue
                if charge <= _EPS:
                    if cooldown <= _EPS:
                        self._laser_held[slot] = True
                        fire[slot] = True
                    continue
                full_charge = max(0.0, self._stat(weapon, "charge", 0.75))
                hold_s = max(0.0, self._stat(weapon, "hold_s", 2.0))
                # Release on a fully charged, verified aim.  If the torso never
                # gets there, release just before the server's automatic shot.
                automatic_release = charge >= full_charge + max(0.0, hold_s - self._decision_dt) - _EPS
                if ((charge >= full_charge - _EPS and candidate["aligned"] and cooldown <= _EPS)
                        or automatic_release or cooldown > _EPS):
                    self._release_laser(slot, charge)
                else:
                    self._laser_held[slot] = True
                    fire[slot] = True

        return {"aim": self._clamped_aim(me, candidates[primary]["desired"]),
                "fire": fire, "reload": reload}
