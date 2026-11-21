import test from "node:test"
import assert from "node:assert/strict"
import { gunzipSync } from "node:zlib"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Brain } from "../src/bot.ts"
import { hello, observation } from "./fixtures.ts"
import type { Observation } from "../src/mechfight.ts"

function bot(): Brain {
  const brain = new Brain(hello())
  brain.map!.los = () => true
  return brain
}
function target(obs: Observation, x = 100, y = 0, charging = false) {
  const me = obs.self
  obs.mechs = [{ id: 5, kind: "mech", pos: [me.pos[0] + x, me.pos[1] + y, 0], vel: [0, 0, 0], aim: [Math.PI, 0], hp: 1400, max_hp: 1400, cubes: 0, weapons: ["gun", "laser"], charging }]
}
function arm(obs: Observation, kind: "laser" | "lightning", charge = 0) {
  const h = hello()
  obs.self.weapons[1] = { kind, cooldown: 0, stats: h.config.weapons[kind], ...(kind === "laser" ? { charge } : {}) }
}

test("laser charging keeps gun lead until the hitscan handoff window", () => {
  const obs = observation()
  obs.self.aim = [Math.PI / 2, 0]
  target(obs, 0, 100)
  obs.mechs[0].vel = [12, 0, 0]
  arm(obs, "laser", 0.3)
  const a = bot().act(obs)
  assert.ok(a.aim![0] < Math.PI / 2 - 0.01, `expected negative gun lead, got ${a.aim![0]}`)
  assert.equal(a.fire![1], true)
})

test("mobility upgrades outrank marginal gun throughput upgrades", () => {
  const obs = observation()
  obs.offer = {
    id: 1,
    expires: 5,
    choices: [
      { id: "gun_damage", name: "Tungsten rounds", desc: "+15% arm gun damage" },
      { id: "servos", name: "Leg servos", desc: "+8% walk and boost speed" },
      { id: "gun_rate", name: "Rotary feed", desc: "+15% arm gun fire rate" },
    ],
  }
  const action = bot().act(obs)
  assert.equal(action.pick, 1)
})

test("a held laser makes laser damage outrank nanites and servos, but not armor", () => {
  const offer = (ids: string[]) => ({ id: 1, expires: 5, choices: ids.map((id) => ({ id, name: id, desc: "" })) })
  const obs = observation()
  arm(obs, "laser")
  obs.offer = offer(["servos", "nanites", "laser_damage"])
  assert.equal(bot().act(obs).pick, 2)
  obs.offer = offer(["laser_damage", "armor"])
  assert.equal(bot().act(obs).pick, 1)
  const noLaser = observation()
  noLaser.offer = offer(["laser_damage", "servos"])
  assert.equal(bot().act(noLaser).pick, 1)
})

test("full aligned laser releases and preserves a lost target's charge", () => {
  const obs = observation()
  obs.self.aim = [Math.PI / 2, 0]
  target(obs, 0, 100)
  arm(obs, "laser", 0.75)
  const a = bot().act(obs)
  assert.equal(a.fire![1], false)
  obs.mechs = []
  obs.t = 0.1
  obs.tick = 2
  const b = bot().act(obs)
  assert.equal(b.fire![1], false)
})

test("lightning uses its direct angle rather than stale gun-lead error", () => {
  const obs = observation()
  obs.self.aim = [Math.PI / 2, 0]
  target(obs, 0, 30)
  arm(obs, "lightning")
  const a = bot().act(obs)
  assert.equal(a.fire![1], true)
})

test("muzzle-blocked targets never authorize gun or laser fire", () => {
  const obs = observation()
  obs.self.aim = [Math.PI / 2, 0]
  target(obs, 0, 100)
  arm(obs, "laser", 0.3)
  const brain = bot()
  brain.map!.los = () => false
  const a = brain.act(obs)
  assert.deepEqual(a.fire, [false, true])
})

test("urgent zone travel cannot be diverted to a nearby weapon", () => {
  const obs = observation()
  obs.self.pos = [500, 0, 0]
  obs.self.in_zone = false
  obs.zone.next_center = [0, 0]
  obs.zone.next_radius = 80
  obs.pickups = [{ id: 8001, kind: "laser", pos: [510, 0, 0] }]
  const a = bot().act(obs)
  assert.ok(a.move![0] < 0, `expected movement toward zone, got ${a.move}`)
})

test("charging laser does not trigger the stuck jet watchdog", () => {
  const obs = observation()
  target(obs, 100, 0)
  arm(obs, "laser", 0.3)
  const brain = bot()
  brain.stuckT = 0.5
  brain.lastPos = [...obs.self.pos]
  const a = brain.act(obs)
  assert.equal(a.jump, false)
})

test("a partial charge without any target is released intentionally", () => {
  const obs = observation()
  arm(obs, "laser", 0.4)
  const a = bot().act(obs)
  assert.equal(a.fire![1], false)
})

test("real replay produces bounded finite actions and fires", () => {
  const kit = process.env.MECHFIGHT_KIT ?? resolve(process.cwd(), "../mechfight-kit")
  const lines = gunzipSync(readFileSync(resolve(kit, "check/stream.jsonl.gz"))).toString("utf8").trim().split("\n")
  const h = JSON.parse(lines[0])
  h.map.dir = resolve(kit, "arena")
  const brain = new Brain(h)
  let shots = 0
  for (const line of lines.slice(1)) {
    const msg = JSON.parse(line)
    if (msg.type !== "obs") continue
    const a = brain.act(msg)
    assert.ok(Number.isFinite(a.aim![0]) && Number.isFinite(a.aim![1]))
      assert.ok(Math.hypot(...a.move!) <= 1.000001, `move=${a.move} tick=${msg.tick}`)
    assert.equal(a.fire!.length, 2)
    shots += Number(a.fire![0]) + Number(a.fire![1])
  }
  assert.ok(shots > 0)
})

test("a nearby crate behind cover is approached instead of idling in place", () => {
  const obs = observation()
  const brain = bot()
  const gz = brain.map!.groundAt(20, 0)
  obs.crates = [{ id: 900, pos: [20, 0, gz], hp: 120 } as any]
  brain.map!.los = () => false
  const a = brain.act(obs)
  assert.ok(Math.hypot(a.move![0], a.move![1]) > 0.5, `expected to move, got ${a.move}`)
})

test("a nearby crate in clear line of fire is still shot from position", () => {
  const obs = observation()
  const brain = bot()
  const gz = brain.map!.groundAt(20, 0)
  obs.crates = [{ id: 900, pos: [20, 0, gz], hp: 120 } as any]
  const a = brain.act(obs)
  assert.equal(Math.hypot(a.move![0], a.move![1]), 0)
})



test("a partial laser charge that already kills is released early; a non-lethal one keeps charging", () => {
  const setup = (hp: number) => {
    const obs = observation()
    const mz = obs.self.stats.muzzle_height ?? 7
    obs.self.aim = [0, Math.atan2(4.5 - mz, 100)]
    target(obs, 100, 0)
    obs.mechs[0].hp = hp
    arm(obs, "laser", 0.3)
    return bot().act(obs)
  }
  // 0.3 s of 0.75 s charge -> (0.35 + 0.65 * 0.4) * 315 = 192 damage
  assert.equal(setup(120).fire![1], false, "lethal partial charge should be released")
  assert.equal(setup(1000).fire![1], true, "non-lethal partial charge should keep charging")
})
