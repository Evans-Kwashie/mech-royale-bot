# Engineering and experiment log

All local scores below are **approximate simulator placement points**, not official scores. The original reported submission is 2.75 at `c0299175d33195f457e9fcbef826a1b94b19fa35`; no replacement official score has been measured.

## Official rules and high-value research

- Official practice is 48 matches against 15 cooperating house bots. Finals are genuine FFAs. Placement gives `16 - place` points; kills matter through power and practice survival.
- r1ver's exact `af337d5` economy controller has a documented official 5.10 (receipt `BB-EAEAF89A`). Its local experiments also show some plausible navigation changes reversing on official results.
- Lance's `171bc06` is documented at 4.54 with quiet movement and 4.75 without it. A charge-aware stuck guard scored 4.79.
- Xero's public A/B work measured a large duel gain from holding triggers through a decision's cooldown boundary, but mixed broader results. Its solo aggression and rooftop experiments often regressed.
- Public implementations repeatedly show that uncontrolled rooftop camping, ceasefire-at-range, and extra combat are not automatic placement improvements.

## Candidate strategy

The MIT TTUN/r1ver economy baseline is retained and extended: keep gun + best special; farm crates/drones/cubes when safe; preserve target focus and weapon detours; prioritize plating/armor/nanites; use cover when losing; avoid late zone damage; use time-sliced Dijkstra ground navigation and jump/jet recovery. A 145 m laser spacing band is being evaluated, not assumed optimal.

Combat fixes include separate gun-lead and hitscan aim solutions, a gun-to-laser handoff near release, explicit lightning direct-aim checks, cooldown-window triggers, and intentional laser hold/release semantics. The two weapons share one torso: one must never be authorized using the other weapon's angle.

## Measured results

| Experiment | Seeds | Result | Decision |
| --- | --- | --- | --- |
| Original c029917 vs Lance, practice engine A | 8 | Original 2.25; Lance 6.875 | Stronger baseline selected |
| Repaired r1ver derivative vs Lance, engine A | 8 | Repaired 5.375; Lance 6.875 | Not adopted as proof of official gain |
| 5.02 research implementation vs repaired derivative, engine A | 24 total | Research 8.125 vs 5.375 (8), 5.1875 vs 3.3125 (16) | Behavioral reference only; unlicensed source excluded |
| 110 -> 145 m laser spacing, full engine | 8 | 6.63 both; kills 4.38 -> 4.13 | Inconclusive, larger experiment needed |
| Candidate pre-FFA, full engine | 16 (201–216) | 7.81, 6.94 kills, 1745 damage taken | Baseline candidate |
| FFA selective disengagement, full engine | Same 16 | 6.81, 5.25 kills | Rejected/reverted |
| Gun-to-laser handoff, full engine | Same 16 | **8.69**, 7.63 kills, 0.93 laser hits | Best measured candidate |
| Candidate vs repaired derivative, practice engine A | 16 (19551–19566) | **5.50 vs 3.375**; +2.125 mean paired delta | Keep pending full regression |
| Candidate vs repaired derivative, FFA engine | 4 spawn-swapped pairs | **11.125 vs 9.375**; delta +1.75 | Small, inconclusive FFA result |
| Final practice process engine, seeds 19551–19566 | 16 | 4.38 vs 4.19; paired delta +0.19 | Weak model; keep pending official score |

## Test and harness audit

An edit to the FFA experiment initially left an undefined helper and generated invalid runs. Those runs were discarded; the selective behavior was removed and clean runs repeated. A second harness issue supplied `/arena` only inside Docker. The FFA process adapter now explicitly forwards the real kit map directory. No red or errored run is used as positive evidence.

The full-mechanics simulator is a third-party research simulator used locally only; it is not an official referee. It has different house policies and some approximate physics. The practice process engine omits economy mechanics. FFA numbers use 14 scripted hunters plus the two candidates, with spawn swapping.

## Remaining work before submission

- Keep all regression tests green and run the official replay with zero late actions.
- Run a Docker sandbox check when a functioning Docker daemon is available. The current WSL installation has no accessible daemon, so this remains unverified locally.
- Submit only after the user/team has reviewed the exact tree; use a distinct commit and preserve `c029917` as rollback. Do not infer an official >5.58 score from these surrogate results.
