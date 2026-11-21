# Attrition-control Mech Royale candidate

## Confirmed result

**Official practice: 5.83**, receipt `BB-82C986AE`, at `15b84389c4e5c005e7feb7052249a7728ba804d2`, selected as the final entry on 2026-11-21. This branch now tests a separate follow-up; the winning commit remains available and selected.

This is a **separate candidate branch** for the Builders Mech Royale track. It preserves the previous TypeScript bot and selected 5.46 rollback on `main`; this branch runs a distinct Go combat/cover controller.

## Provenance

The runtime is the MIT-licensed Kanyaraasi/giddygiddyboy lineage at public revision `24d68e50ecd1ecb272b614b8a38c509bc8eeee5f`. Its documentation attributes a **5.81 official practice aggregate** to the underlying `c6f6ad8` control. That score belongs to the original authors, not to this repository or this candidate. Our local comparison of this exact runtime passed the official replay and beat the previous 5.46 TypeScript controller in one 16-seed approximate practice comparison, 5.125 to 4.50. These local points are not official results.

`LICENSE` contains Team Kanyaraasi's MIT notice. `THIRD_PARTY_LICENSES` retains the giddygiddyboy notice. The protocol map is supplied by the scorer, not bundled here.

## Validation

- Exact runtime compiled with Go 1.26.1.
- Official protocol replay: 300/300 timely responses, max 2.3 ms on the validation host, zero late actions.
- Paired practice engine: 5.125 vs 4.50 over 16 seeds, 8 candidate wins, 6 losses, 2 ties.
- Paired practice engine is approximate; official score remains unmeasured.

## Build

The root multi-stage Dockerfile builds a static linux/amd64 binary with the pinned Go 1.26.1 image and runs it as uid 65534 in a scratch image. No runtime downloads or third-party Go modules are needed.

```sh
docker build --platform linux/amd64 -t attrition-control .
python3 /path/to/mechfight-kit/check/check.py --map-dir /arena -- docker run --rm -i \
  --network none --cpus 1 --memory 512m --read-only \
  --tmpfs /tmp:rw,size=64m --user 65534:65534 \
  -v /path/to/mechfight-kit/arena:/arena:ro attrition-control
```

Submit this branch only as an official experiment. Keep `f1affd7cb902` (the 5.46 TypeScript entry) selected unless the official result improves it.
