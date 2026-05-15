---
description: CLI-safety-belt-flaggor (env eller andra) defaultar till OFF. Dry-run/no-op-default uttrycks via avsaknad av en --apply/--write/--commit-flagga, inte via en env-default som tvingar operatören att explicit slå av safety-belten för att flaggan ska fungera.
alwaysApply: true
---

# CLI-safety-belt-defaults

## Grundregel

När ett script har både:

- en CLI-flagga som beskriver "do the destructive thing" (`--apply`,
  `--write`, `--commit`, `--delete`), och
- en env-variabel som beskriver "operatörs-safety-belt" (t.ex.
  `*_DRY_RUN`, `*_READONLY`, `*_DISABLE_WRITE`),

ska env-variabeln defaulta till **OFF/inaktiv** när den är osatt.
CLI-flaggan ensam ska räcka för att utlösa den destruktiva åtgärden.

## Felmönstret

```python
# BAD - operatören måste explicit sätta env=false för att --apply ska fungera
dry_run_env = _env_flag(os.environ.get("MY_DRY_RUN"), default=True)
apply = args.apply and not dry_run_env
```

Detta gör `--apply` till en tyst no-op i den vanligaste operatörs-flödet
(env osatt). Help-texten lovar radering, koden levererar ingenting.
Operatören får ingen tydlig signal att safety-belten är på.

## Rätt mönster

```python
# GOOD - env defaultar till inaktiv; CLI-flagga räcker
dry_run_env = _env_flag(os.environ.get("MY_DRY_RUN"), default=False)
apply = args.apply and not dry_run_env
```

Med detta:

- `script.py` ensamt → dry-run (ingen `--apply`).
- `script.py --apply` → faktisk åtgärd.
- `MY_DRY_RUN=true script.py --apply` → safety-belt aktiv, dry-run.
- `MY_DRY_RUN=false script.py --apply` → faktisk åtgärd (samma som unset).

Safety-belten är opt-in, inte opt-out.

## Test-disciplin

Lås båda riktningarna:

- ett test som verifierar att `--apply` med env osatt **faktiskt
  raderar/skriver**;
- ett test som verifierar att `MY_DRY_RUN=true` blockerar `--apply`.

Utan första testet kan en framtida refactor återinföra felmönstret
utan att en enda regression failar - precis det som hände i
`scripts/prune_generated_previews.py` Finding 1 (post-push review,
2026-05-15).
