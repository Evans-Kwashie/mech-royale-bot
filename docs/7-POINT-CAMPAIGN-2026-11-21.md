# 7-point campaign — 2026-11-21

## Decision

Keep the production bot logic at `3fd07bebc667741893920a0286f1e5f2b8a01420` (`3fd07be`). The user-reported official practice score is 5.23. No strategy experiment below generalized well enough to justify replacing it.

This branch adds validation automation and this experiment record. It does not change `src/bot.ts`, `src/map.ts`, or the submission Dockerfile.

## Runtime and regression validation

GitHub Actions run: [44901094950](https://github.com/Evans-Kwashie/mech-royale-bot/actions/runs/44901094950)

- TypeScript tests: 8/8 passed
- Python regression tests: 9/9 passed
- Official host protocol replay: 300/300 valid and timely actions; zero late actions; PASS
- Docker image built successfully
- Official protocol replay inside the competition-style Docker sandbox: 300/300 valid and timely actions; zero late actions; PASS
- Docker sandbox flags: linux/amd64, no network, 1 CPU, 512 MB memory, read-only root, 64 MB writable /tmp, uid 65534
- Docker replay latency on the hosted runner: p50 0.5 ms, p90 0.7 ms, p99 8.8 ms, max 46.4 ms
- Approximate 16-seed practice simulator: candidate 4.75 vs repaired r1ver baseline 4.4375; 3 wins, 12 ties, 1 loss; mean delta +0.3125

The protocol replay verifies compliance and runtime, not gameplay strength. The local simulator is approximate and is not the official referee.

## Rejected strategy experiments

All experiments changed one parameter in temporary local copies only. No temporary variant was committed.

| Experiment | Seeds | Mean delta vs current candidate | Decision |
|---|---:|---:|---|
| Laser preferred distance 110 m | 19551–19566 | +1.125 | Rejected: fresh block 19567–19582 was -0.25 |
| Laser preferred distance 125 m | 19567–19574 | 0.00 | No effect |
| Laser preferred distance 160 m | 19567–19582 | -0.0625 | No effect / slight regression |
| Low-HP target penalty 90 → 150 | 19551–19558 | +0.875 | Rejected: fresh 19583–19598 was -0.5625 |
| Attacker-retaliation weight ×1.5 | 19551–19558 | +1.50 | Rejected: fresh 19567–19574 was -0.50 |

Each apparent positive was driven by one or two seeds and did not hold up consistently on fresh seeds.

## FFA approximation

Local 16-player FFA league with 14 scripted hunters and spawn-slot swaps:

- Seeds 401–404 (8 games): candidate 10.75 points, baseline 10.50; mean paired delta +0.25
- Seeds 405–412 (16 games): candidate 10.9375, baseline 11.1875; mean paired delta -0.25
- Combined (24 games): candidate 10.875, baseline 10.9583; essentially tied

This is not the official finals environment and is not evidence of a meaningful FFA improvement.

## Submission status

The public competition page displays a sign-in requirement for submissions. The remote browser session used for inspection was not authenticated, so no official practice submission was made from that session. The existing official score of 5.23 remains the only confirmed gameplay score for this candidate.

## Next decision gate

Only adopt a strategy change after it beats the current bot on multiple fresh, paired seed blocks and then improves an official practice submission. Do not infer a 7.00 from protocol tests or local simulator points.
