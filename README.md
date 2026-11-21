# Mech Royale bot

Python 3 and Node.js 24+/Bun 1.4 implementation of the `mechfight/1` protocol. The production entrypoint is `bot.ts`; the container uses only the pinned Bun runtime and the organizer-provided map.

## Architecture

The controller is split into explicit state, strategy, navigation, and combat stages inside `src/bot.ts`, backed by the terrain/prism model in `src/map.ts`:

1. **State estimation:** persistent mech tracks, attackers, damage/sound bearings, weapon/cube/NPC memories, and target hysteresis.
2. **Strategy:** zone, fight/retreat, cover/heal, weapon/cube/NPC/crate/supply-drop goals, with separate selective engagement after confirmed free-for-all evidence.
3. **Navigation:** ground clearance checks and time-sliced Dijkstra paths, local combat steering, and jump/jet recovery.
4. **Combat:** actual-torso aiming, predictive gun lead, shared-torso gun/laser arbitration, laser charge/release, lightning cones, and mortar solutions.
5. **Execution:** bounded path work, one protocol-valid action per observation, and wrapper fallback/coasting on errors.

## Provenance

The starting controller is the MIT-licensed TTUN/r1ver economy implementation at `af337d5c1275d03478685bd4936c8a551fa6b200`. r1ver records **5.10 official practice points** for that exact revision (receipt `BB-EAEAF89A`). That is their result, not this repository's score. The submitted `c029917` Evans bot (reported 2.75) is preserved in `baselines/original/`; the r1ver baseline is in `baselines/r1ver/`. Relevant copyright notices are retained in `LICENSE` and `baselines/r1ver/LICENSE`.

Research and negative results are documented in `docs/EXPERIMENTS.md`. An unlicensed third-party implementation was used only as behavioral research; none of its source is included in production.

## Tests

Set `MECHFIGHT_KIT` to an extracted official starter kit, then:

```sh
python3 -m unittest discover -v
python3 "$MECHFIGHT_KIT/check/check.py" -- node bot.ts
```

Local practice and free-for-all simulators are approximate, not official score predictors:

```sh
python3 tools/eval/simulate.py --kit "$MECHFIGHT_KIT" \
  --bot bot.ts --baseline baselines/r1ver/bot.ts --seed 19551 --matches 16 \
  --output eval-results/candidate-vs-r1ver.json
python3 tools/eval/ffa_league.py --kit "$MECHFIGHT_KIT" \
  --bot bot.ts --baseline baselines/r1ver/bot.ts --seed 601 --pairs 8 \
  --output eval-results/ffa-candidate-vs-r1ver.json
```

The official scorer alone determines the 48-match practice score. Docker conformance must be run with the map mounted at `/arena`, no network, one CPU, 512 MB RAM, read-only root, and uid 65534.
