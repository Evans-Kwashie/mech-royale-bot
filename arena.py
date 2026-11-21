"""Static campus geometry: walkability grid, routes, and line of fire.

All expensive map indexing happens during the hello/ready phase.  The hot path
only queries cached grid cells and a small list of nearby building prisms.
"""
from __future__ import annotations

import heapq
import json
import math
import os
import struct
import time


class Arena:
    def __init__(self, map_dir: str):
        with open(os.path.join(map_dir, "v2", "world.json"), encoding="utf-8") as f:
            self.world = json.load(f)
        b = self.world["bounds"]
        self.bounds = (b["minX"], b["minY"], b["maxX"], b["maxY"])
        t = self.world["terrain"]
        self.terrain_info = t
        with open(os.path.join(map_dir, "v2", "terrain.i16"), "rb") as f:
            self.terrain = struct.unpack("<%dh" % (t["nx"] * t["ny"]), f.read())

        self.prisms = []
        self.grid = {}
        cell = 24
        for p in self.world["prisms"]:
            ring = p["ring"]
            xs, ys = ring[::2], ring[1::2]
            q = dict(p)
            q["bbox"] = (min(xs), min(ys), max(xs), max(ys))
            self.prisms.append(q)
            x0, y0 = math.floor(min(xs) / cell), math.floor(min(ys) / cell)
            x1, y1 = math.floor(max(xs) / cell), math.floor(max(ys) / cell)
            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    self.grid.setdefault((gx, gy), []).append(q)

        # A conservative 5 m planning grid, including the mech's radius.
        self.step = 5.0
        self.min_x, self.min_y, self.max_x, self.max_y = self.bounds
        self.nx = int((self.max_x - self.min_x) / self.step) + 1
        self.ny = int((self.max_y - self.min_y) / self.step) + 1
        self.free = bytearray(self.nx * self.ny)
        margin = 4.0
        for j in range(self.ny):
            y = self.min_y + j * self.step
            for i in range(self.nx):
                x = self.min_x + i * self.step
                # Stay a mech-radius away from the absolute map wall.
                if (x < self.min_x + 4 or x > self.max_x - 4
                        or y < self.min_y + 4 or y > self.max_y - 4):
                    continue
                z = self.height(x, y)
                if (not self.blocked(x, y, z + 4.5, radius=3.5)
                        and self._clear_terrain(x, y, z, margin)):
                    self.free[j * self.nx + i] = 1
        self.los_cache = {}
        self.route_cache = {}

    def height(self, x: float, y: float) -> float:
        """Bilinear terrain sample in metres."""
        t = self.terrain_info
        u = max(0.0, min(t["nx"] - 1.001, (x - t["minX"]) / t["step"]))
        v = max(0.0, min(t["ny"] - 1.001, (y - t["minY"]) / t["step"]))
        i, j = int(u), int(v)
        a, b = u - i, v - j
        n = t["nx"]
        k = j * n + i
        h00, h10 = self.terrain[k], self.terrain[k + 1]
        h01, h11 = self.terrain[k + n], self.terrain[k + n + 1]
        return ((h00 * (1 - a) + h10 * a) * (1 - b)
                + (h01 * (1 - a) + h11 * a) * b) * t["scale"]

    @staticmethod
    def _inside(ring, x: float, y: float) -> bool:
        inside = False
        j = len(ring) - 2
        for i in range(0, len(ring), 2):
            xi, yi, xj, yj = ring[i], ring[i + 1], ring[j], ring[j + 1]
            if (yi > y) != (yj > y):
                cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < cross:
                    inside = not inside
            j = i
        return inside

    @classmethod
    def _in_prism(cls, p, x: float, y: float) -> bool:
        if not cls._inside(p["ring"], x, y):
            return False
        return not any(cls._inside(h, x, y) for h in p.get("holes", []))

    def prisms_near(self, x: float, y: float, distance: float = 0.0):
        if distance <= 24:
            keys = [(math.floor(x / 24), math.floor(y / 24))]
        else:
            r = math.ceil(distance / 24)
            gx, gy = math.floor(x / 24), math.floor(y / 24)
            keys = [(gx + i, gy + j) for i in range(-r, r + 1)
                    for j in range(-r, r + 1)]
        result, seen = [], set()
        for key in keys:
            for p in self.grid.get(key, ()):
                if id(p) not in seen:
                    seen.add(id(p))
                    result.append(p)
        return result

    def blocked(self, x: float, y: float, z: float, radius: float = 0.0) -> bool:
        """True if a standing mech/body sphere intersects a solid prism."""
        for p in self.prisms_near(x, y):
            x0, y0, x1, y1 = p["bbox"]
            if x < x0 - radius or x > x1 + radius or y < y0 - radius or y > y1 + radius:
                continue
            # Ground-only planning treats every bridge footprint as blocked.
            # Some decks are too low to clear a mech even where their base is
            # above the local terrain; omitting these tiny shortcuts is safe.
            if p["kind"] == "bridge":
                if self._in_prism(p, x, y):
                    return True
                if radius:
                    for k in range(8):
                        a = k * math.tau / 8
                        if self._in_prism(p, x + radius * math.cos(a), y + radius * math.sin(a)):
                            return True
                continue
            if z > p["top"] + 0.2 or z + 4.5 < p["base"]:
                continue
            # Test the centre and eight perimeter points.  This is only used
            # while constructing the static grid, not in the decision loop.
            if self._in_prism(p, x, y):
                return True
            if radius:
                for k in range(8):
                    a = k * math.tau / 8
                    if self._in_prism(p, x + radius * math.cos(a), y + radius * math.sin(a)):
                        return True
        return False

    def _clear_terrain(self, x: float, y: float, z: float, r: float) -> bool:
        # Reject steep one-cell terrain discontinuities and tiny river islands.
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
            h = self.height(x + dx, y + dy)
            if abs(h - z) > r * 1.12:
                return False
        return True

    def _grid_point(self, node):
        i, j = node
        return self.min_x + i * self.step, self.min_y + j * self.step

    def _node(self, x: float, y: float):
        return (round((x - self.min_x) / self.step), round((y - self.min_y) / self.step))

    def _valid(self, n) -> bool:
        i, j = n
        return 0 <= i < self.nx and 0 <= j < self.ny and self.free[j * self.nx + i]

    def nearest_free(self, x: float, y: float):
        n = self._node(x, y)
        if self._valid(n):
            return n
        for r in range(1, 13):
            best, score = None, float("inf")
            for i in range(n[0] - r, n[0] + r + 1):
                for j in range(n[1] - r, n[1] + r + 1):
                    if max(abs(i - n[0]), abs(j - n[1])) != r:
                        continue
                    if self._valid((i, j)):
                        px, py = self._grid_point((i, j))
                        d = (px - x) ** 2 + (py - y) ** 2
                        if d < score:
                            best, score = (i, j), d
            if best:
                return best
        return None

    def walkable(self, a, b) -> bool:
        """Grid segment test used to smooth A* paths."""
        a, b = a[:2], b[:2]
        d = math.dist(a, b)
        count = max(1, math.ceil(d / (self.step * 0.48)))
        previous = None
        for k in range(count + 1):
            f = k / count
            n = self._node(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if n != previous and not self._valid(n):
                return False
            previous = n
        return True

    def route(self, start, goal, max_expand: int = 5000):
        """Return smoothed world XY waypoints, excluding start."""
        start, goal = start[:2], goal[:2]
        s, g = self.nearest_free(*start), self.nearest_free(*goal)
        if s is None or g is None:
            return [tuple(goal)]
        key = (s, g)
        if key in self.route_cache:
            return self.route_cache[key]
        sp, gp = self._grid_point(s), self._grid_point(g)
        if self.walkable(start, goal):
            return [tuple(goal)]
        if self.walkable(start, sp) and self.walkable(sp, gp) and self.walkable(gp, goal):
            return [sp, gp, tuple(goal)]

        started = time.perf_counter()
        open_heap = [(0.0, 0.0, s)]
        cost = {s: 0.0}
        parent = {}
        found = None
        expansions = 0
        neighbors = ((-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1),
                     (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414))
        while open_heap and expansions < max_expand:
            if expansions & 127 == 0 and time.perf_counter() - started > 0.012:
                break
            _, current_cost, cur = heapq.heappop(open_heap)
            if current_cost > cost.get(cur, float("inf")) + 1e-8:
                continue
            if cur == g:
                found = cur
                break
            expansions += 1
            for di, dj, multiplier in neighbors:
                nxt = cur[0] + di, cur[1] + dj
                if not self._valid(nxt):
                    continue
                if di and dj and (not self._valid((cur[0] + di, cur[1]))
                                  or not self._valid((cur[0], cur[1] + dj))):
                    continue
                new_cost = current_cost + multiplier * self.step
                if new_cost < cost.get(nxt, float("inf")):
                    cost[nxt] = new_cost
                    parent[nxt] = cur
                    priority = new_cost + math.dist(nxt, g) * self.step
                    heapq.heappush(open_heap, (priority, new_cost, nxt))
        if found is None:
            # Follow the explored node with the smallest heuristic distance,
            # never a straight segment through solid geometry.
            if cost:
                found = min(cost, key=lambda n: (math.dist(n, g), cost[n]))
                if found == s:
                    return [sp]
            else:
                return [sp]
        nodes = [found]
        while nodes[-1] != s:
            nodes.append(parent[nodes[-1]])
        nodes.reverse()
        points = [sp] + [self._grid_point(n) for n in nodes[1:]]
        points.append(tuple(goal))
        # Greedy line-of-walk smoothing greatly reduces grid zig-zag.
        result = []
        anchor = tuple(start)
        i = 0
        while i < len(points):
            furthest = i
            for j in range(i + 1, len(points)):
                if self.walkable(anchor, points[j]):
                    furthest = j
                else:
                    break
            result.append(points[furthest])
            anchor = points[furthest]
            i = furthest + 1
        if len(self.route_cache) > 1024:
            self.route_cache.clear()
        self.route_cache[key] = result
        return result

    def clear_shot(self, origin, target) -> bool:
        """Buildings/terrain block shots; trees deliberately do not."""
        key = (tuple(round(v, 1) for v in origin), tuple(round(v, 1) for v in target))
        if key in self.los_cache:
            return self.los_cache[key]
        distance = math.dist(origin, target)
        count = max(1, math.ceil(distance / 4.0))
        result = True
        for k in range(1, count):
            f = k / count
            x = origin[0] + (target[0] - origin[0]) * f
            y = origin[1] + (target[1] - origin[1]) * f
            z = origin[2] + (target[2] - origin[2]) * f
            if z < self.height(x, y) + 0.05:
                result = False
                break
            # Checking the body centre at this height is enough for LOS.  Do
            # not apply the standing-body test used by walkability.
            for p in self.prisms_near(x, y):
                if p["base"] - 0.05 <= z <= p["top"] + 0.05 and self._in_prism(p, x, y):
                    result = False
                    break
            if not result:
                break
        if len(self.los_cache) > 8192:
            self.los_cache.clear()
        self.los_cache[key] = result
        return result
