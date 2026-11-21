# Submission handoff — 2026-11-21

## Recommended action

**Submit the current tree as the next official practice candidate.** It is protocol-tested and has substantially stronger local results than the original 2.75 bot. Its official score is **unknown**; no official match has been submitted by this session. Do not select it over the original best unless the official result supports that decision.

The original submitted revision remains available at:

```text
c0299175d33195f457e9fcbef826a1b94b19fa35
```

The new work is currently **uncommitted in the working tree**. No commit, push, website submission, or other Git mutation was performed. To publish, the team must explicitly run:

```sh
git add Dockerfile .dockerignore .gitignore LICENSE README.md HANDOFF.md package.json bot.ts src tests docs baselines tools
# Review the staged tree, then explicitly choose to commit:
git commit -m "Improve Mech Royale economy and shared weapon control"
git push origin HEAD:main
```

Submit `https://github.com/Evans-Kwashie/mech-royale-bot/` on the official Mech Royale page. The image builds from the root `Dockerfile` and runs `bot.ts` with Bun 1.4.4. Keep this new commit and the original revision publicly fetchable.

## Candidate implementation

- Economy-first licensed TTUN/r1ver lineage: gun + best special, cube/weapon detours, crates/drones/drops, plating/armor/nanites priority.
- Terrain/prism collision and line-of-fire checks, time-sliced ground navigation, local combat steering, jump/jet recovery.
- Target memory, attacker priority, focus hysteresis, selective retreat/cover, and 145 m laser engagement spacing.
- Separate predictive gun-lead and hitscan aim; gun-to-laser handoff shortly before release.
- Lightning fires using its own direct angle and cooldown window; laser charges/releases without using the gun's angle.
- Rounded movement vectors are clamped to protocol magnitude <= 1.
- Important source: MIT TTUN/r1ver `af337d5` (r1ver's independently reported official 5.10), with its later repair ideas and new engineering changes. Third-party unlicensed source was used only as behavioral research and is not included.

## Actual verification completed

| Check | Result |
| --- | --- |
| New Node regression tests | **8/8 PASS** (`MECHFIGHT_KIT=/path/to/kit npm test`) |
| Original Python regression tests | **9/9 PASS** (`python3 -m unittest discover -v`) |
| Official `check.py`, Node 24 | **PASS**, 300/300 on time, p50 0.6 ms, p90 0.9 ms, p99 13.4 ms, max 16.8 ms |
| Full-mechanics research simulator, seeds 201–216 | **8.69 local points**, 7.50 kills/match, 106.88 s mean survival, 5.06 cubes/match, 0.74 gun and 0.92 laser hit rates, zero late decisions |
| Genuine-FFA local runner, 4 spawn-swapped pairs | Candidate **11.125**, repaired baseline **9.375**, delta +1.75 (small sample, approximate opponents) |
| Separate full-engine FFA check, seeds 301–308 | **12.38 local points**, 3.13 kills, 148.88 s survival, 8.50 cubes; zero late decisions (approximate FFA opponents) |
| Practice process engine, 16 seeds | **4.38 candidate vs 4.19 repaired baseline** (+0.19); weak/different model without economy, not an official score |
| Docker sandbox | **NOT RUN**: WSL Docker CLI exists, but its daemon/WSL integration is unavailable |

Local numbers are not predictions of an official >5.58 score. Practice and FFA opponents differ materially from both simulators.

## Commands to reproduce

From this repository with the official kit extracted:

```sh
python3 -m unittest discover -v
MECHFIGHT_KIT=/path/to/mechfight-kit npm test
python3 /path/to/mechfight-kit/check/check.py -- node bot.ts
```

After enabling Docker Desktop WSL integration, the remaining submission gate is:

```sh
docker build -t mech-royale-candidate .
python3 /path/to/mechfight-kit/check/check.py --map-dir /arena -- docker run --rm -i \
  --network none --cpus 1 --memory 512m --read-only \
  --tmpfs /tmp:rw,size=64m --user 65534:65534 \
  -v /path/to/mechfight-kit/arena:/arena:ro mech-royale-candidate
```

## Remaining weaknesses / next session

1. Obtain the actual official practice score and record the receipt and exact submitted commit in `docs/EXPERIMENTS.md`.
2. Run the Docker sandbox gate before final submission if at all possible. The host-only replay is not equivalent to the sandboxed Bun container.
3. FFA evidence is only four paired scenarios and positive; expand to at least 32 fresh spawn-swapped pairs before tuning specifically for finals.
4. No meaningful FFA-selective policy is active: the tested disengagement experiment reduced the squad-simulator result from 7.81 to 6.81 and was reverted. Do not reintroduce it without controlled evidence.
5. Ground-only loot and roof climbing are approximate; rooftop camping and long roof detours have repeatedly regressed other competitors' official scores.
6. Existing cover navigation, mortar aiming, projectile dodging, and supply capture remain heuristic. Test concrete bugs individually; avoid a wholesale rewrite or reinforcement learning under the deadline.
7. The official page exposes only aggregate scores. Do not claim individual death causes, per-seed placements, or score gains from the website unless supplied separately.
