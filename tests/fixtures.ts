import { gunzipSync } from "node:zlib"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import type { Hello, Observation } from "../src/mechfight.ts"

export function hello(): Hello {
  const kit = process.env.MECHFIGHT_KIT ?? resolve(process.cwd(), "../mechfight-kit")
  const path = resolve(kit, "check/stream.jsonl.gz")
  const first = gunzipSync(readFileSync(path)).toString("utf8").split("\n", 1)[0]
  const result = JSON.parse(first) as Hello
  result.map.dir = resolve(kit, "arena")
  return result
}

export function observation(): Observation {
  const h = hello()
  return {
    type: "obs", tick: 0, t: 0, alive: 16,
    self: {
      id: 0, pos: [0, 0, 0], vel: [0, 0, 0], aim: [0, 0], hp: 1400, max_hp: 1400,
      energy: 100, max_energy: 100, grounded: true, cubes: 0, upgrades: [],
      weapons: [{ kind: "gun", cooldown: 0, ammo: 12, reload: 0, stats: h.config.weapons.gun }, null],
      in_zone: true, stats: { ...h.config.mech },
    },
    mechs: [], projectiles: [], crates: [], cubes: [], pickups: [], sounds: [], beams: [], events: [], drops: [],
    zone: { center: [0, 0], radius: 560, next_center: [0, 0], next_radius: 380, shrink_start: 60, shrink_end: 110, dps: 20 },
    offer: null,
  }
}
