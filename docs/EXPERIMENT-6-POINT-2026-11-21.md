# 6-point candidate — 2026-11-21

## Control

Official selected practice entry: **5.46**, receipt `BB-417962FB`, commit `f1affd7cb902`. That source is preserved in `baselines/control546/` and in Git history. Later official experiments at 5.21, 5.15, and 5.33 did not replace it.

## Candidate

- Preserve invested laser charge when a target disappears from current tracking. The previous fallback immediately released it and could waste a nearly charged shot.
- Use independent strafe RNG salt `0xc2b2ae35`. This intentionally changes combat trajectories rather than pretending to be a deterministic policy improvement.
- Keep the 5.46 controller's laser-upgrade and crate-navigation fixes.
- No exposed-body aiming experiment: a separate test regressed the paired practice model from 4.9375 to 4.1875 and was removed.
- No alternate Go controller: a licensed fallback passed protocol timing (max 2.0 ms) but lost its paired practice comparison 2.625 to 5.375 and was discarded.

## Validation

- Node regression tests: **12/12 PASS**.
- Original Python regression tests: **9/9 PASS**.
- Official protocol replay: **300/300 on time**, max 20.7 ms; zero malformed actions.
- Full-mechanics research simulator, seeds 201–216: **9.00** local points, 8.19 kills/match, 105.81 s mean survival, 5.44 cubes, 0.79 gun and 0.96 laser hit rates, zero late decisions.
- Paired practice process engine, seeds 19551–19558: **7.125 candidate vs 6.50 control**, mean delta +0.625 (8 seeds).
- Separate fresh full-engine block, seeds 301–316: laser-continuity and RNG variants individually scored around 7.44–7.50 vs control 6.69–6.94; results are approximate and timing-sensitive.

These are **not official 6.0 results**. Only the official 48-match practice run can decide whether this candidate should replace the 5.46 final selection.

## Next decision

Submit the exact new commit as the next official attempt. If it does not improve the official score, retain `f1affd7` and do not select this candidate. Avoid further unvalidated threshold churn; use fresh controlled experiments or a genuinely different validated combat policy.
