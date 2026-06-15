# Beslutsregister (ADR-index)

Snabb karta över ADR:erna i denna mapp så en agent slipper läsa alla 60. Indexet
är en orientering, inte sanningskälla — sanningen bor i själva ADR-filerna +
git/koden. Vid tvekan om ett äldre beslut fortfarande gäller: läs ADR:n + ev.
senare ADR som rör samma yta.

## Aktiva beslut (läs dessa)

De senaste operativa besluten (0040–0060), aktiva om inget annat anges:

- [0040 komponentkatalog](0040-component-catalog.md)
- [0041 varm sandbox-reuse](0041-vercel-sandbox-warm-reuse.md)
- [0042 galleri-inline-flytt (ecommerce)](0042-gallery-inline-move-ecommerce.md)
- [0043 section-content-overrides](0043-section-content-overrides.md)
- [0044 soul-runtime + identitetsvy](0044-soul-runtime-and-identity-view.md)
- [0045 branschprofiler (sni)](0045-sni-industry-profiles.md)
- [0046 sektionsmarkering som followup-signal](0046-section-marking-followup-signal.md)
- [0047 generativ sektionsomskrivning (editplan)](0047-section-content-rewrite-editplan.md)
- [0048 hostat bygge i sandbox](0048-hosted-build-python-i-sandbox.md)
- [0049 kv-store-adapter](0049-kv-store-adapter.md)
- [0050 publik hostad viewser + rate-limit](0050-publik-hostad-viewser-med-rate-limit.md)
- [0051 dirigentpult + pris-snapshot](0051-dirigentpult-styrsida-och-pris-snapshot.md)
- [0052 per-roll-modellparametrar](0052-per-roll-modellparametrar.md)
- [0053 hard-dossier-kontrakt](0053-hard-dossier-kontrakt.md)
- [0054 komponentintag (mcp-grind)](0054-komponentintag-mcp-grind.md)
- [0055 hostad preview-standardisering](0055-hostad-preview-standardisering.md)
- [0056 dossier-dependencies](0056-dossier-dependencies.md)
- [0057 component-builder-rollkontrakt](0057-component-builder-rollkontrakt.md)
- [0058 preview-bundle-tarball](0058-preview-bundle-tarball.md)
- [0059 component-builder katalog-mount](0059-component-builder-catalog-mount.md) — utkast/proposed, ej beslutat
- [0060 route/nav-mutation v1](0060-route-nav-mutation-v1.md)

Live preview-runtime-beslut (äldre men gällande):

- [0030 preview/deploy-providers är adapters](0030-preview-provider-portability.md)
- [0033 vercel-sandbox primär preview-runtime](0033-vercel-sandbox-primary-preview.md) — local-next fallback, stackblitz pausad

Fundament (gäller fortfarande): [0001 policies som sanningskälla](0001-policies-as-source-of-truth.md),
[0006 term-disciplin](0006-term-discipline.md), [0007 språkpolicy](0007-language-policy.md).

## Historik / superseded

Omkullkastade beslut — radera aldrig filerna, men följ den senare ADR:n:

- [0003 preview-runtime stackblitz-först](0003-preview-runtime-stackblitz-first.md) — superseded av 0033 (vercel-sandbox primär, stackblitz pausad; abstraktionen lever vidare)
- [0021 stackblitz payload-workarounds](0021-stackblitz-preview-payload-workarounds.md) — superseded av 0033 (stackblitz-vägen pausad)
- [0025 browser-fallback för preview](0025-browser-fallback-preview.md) — superseded av 0033 (var proposed; B125 löst av vercel-sandbox)

Övriga 0002, 0004–0005, 0008–0029, 0031–0039 är sprint-/fundamentbeslut som inte
gåtts igenom individuellt i detta index-pass; behandla dem som gällande tills en
senare ADR säger annat. Full lista: filerna i denna mapp + `git log`.
