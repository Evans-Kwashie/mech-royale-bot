# 7-point candidate experiment — 2026-11-21

## Candidate

Branch: `build/7-point-candidate`  
Base: `83b304f` (the validated 5.23 production candidate plus the campaign CI/report merge)

Gameplay change: reorder upgrade preferences so health, regeneration, movement speed, and energy sustain are selected before marginal weapon-throughput upgrades. The candidate keeps the existing combat, navigation, and weapon-control policy unchanged.

## Why this change

The game awards placement, not kill count. The previous fixed upgrade list selected gun/laser/lightning throughput before `servos`, `capacitor`, `reactor`, and `jets`. Mobility and energy sustain can help preserve distance, escape focus fire, and remain inside the safe zone. This is a targeted survival hypothesis, not a claim that these upgrades are always superior in every build.

## Local FFA evidence

Compared against the unchanged baseline with two spawn-swapped games per seed, in a local 16-player simulator with 14 scripted hunters:

| Seed block | Paired seeds | Games | Candidate mean | Baseline mean | Mean delta |
|---|---:|---:|---:|---:|---:|
| 401–404 | 4 | 8 | 11.125 | 10.375 | +0.750 |
| 405–412 | 8 | 16 | 11.0625 | 10.9375 | +0.125 |
| 421–428 | 8 | 16 | 11.4375 | 10.875 | +0.5625 |
| **Combined** | **20** | **40** | **11.225** | **10.800** | **+0.425** |

An alternate ordering that put servos ahead of nanites and jets ahead of capacitor/reactor regressed on seeds 413–420 (-1.25 points per paired seed) and was rejected. These are surrogate FFA results, not official practice scores or a prediction of a 7.00 result.

## Validation

- TypeScript policy tests: **9/9 pass**, including a new test that asserts servos outrank gun damage/rate when offered together.
- Python regression tests: **9/9 pass**.
- Official starter-kit protocol replay: **300/300 responses**, zero late actions, zero missed 50 ms decisions, p99 10.3 ms and max 29.3 ms on the test machine.
- Docker build/sandbox replay: **not yet rerun for this candidate**. The current remote shell does not provide Docker; rerun the existing GitHub Actions workflow after publishing this branch.
- Official practice score: **not yet measured**. The previously reported 5.23 belongs to the baseline candidate, not this experimental branch.

## Decision

Keep the candidate isolated from `main` until the competition's official practice score is measured. The +0.425 local FFA improvement is enough to justify an official test, not enough to claim a 7.00 bot.
