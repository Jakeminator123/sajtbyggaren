# SNI 2025 (Svensk näringsgrensindelning)

Canonical bransch-taxonomi från SCB. Repot håller en deterministisk
JSON-spegel som canonical referens; Excel-källan är operatör-lokal och
committas inte.

## Filer i denna mapp

| Fil | Roll | Spårning |
|-----|------|----------|
| [`sni-2025.v1.json`](sni-2025.v1.json) | Deterministisk JSON-spegel, 1882 items (22 avdelningar, 87 huvudgrupper, 287 grupper, 651 undergrupper, 835 detaljgrupper) | Committad. Canonical referens. |
| `sni-2025*.xlsx` (lokalt) | SCB:s Excel-källa som operatören laddat ner | Gitignored (`data/taxonomies/**/*.xlsx`). Tas bort efter extraktion. |

JSON:en är exkluderad från Cursors sökindex (samma kategori som
lockfiles, se [`.cursorindexingignore`](../../../.cursorindexingignore))
för att inte blåsa upp agentens kontext med ~25 000 rader repetitiv
branschstruktur. Använd [`scripts/lookup_sni.py`](../../../scripts/lookup_sni.py)
för uppslagning istället.

## JSON-struktur

```json
{
  "taxonomyId": "sni-2025",
  "version": 1,
  "sourceFile": "data/taxonomies/sni/sni-2025.source.xlsx",
  "descriptionSv": "...",
  "levels": {
    "section": "Avdelning",
    "division": "Huvudgrupp",
    "group": "Grupp",
    "class": "Undergrupp",
    "subclass": "Detaljgrupp"
  },
  "items": [
    {
      "code": "56110",
      "level": "subclass",
      "labelSv": "Restaurangverksamhet",
      "parentCode": "5611",
      "sectionCode": "I",
      "path": ["I", "56", "561", "5611", "56110"]
    }
  ]
}
```

Items är sorterade deterministiskt (section först, sedan stigande kod
inom nivå). `path` är canonical breadcrumbs så konsumenter slipper
rebuilda hierarkin.

**Notera:** `sourceFile`-fältet dokumenterar extractor-konventionen
(`sni-2025.source.xlsx`) och är inte en aktiv filreferens. Excel-källan
existerar inte i versionskontrollen — den är ephemeral input som tas
bort efter extraktion.

## Bygg om JSON-spegeln

När SCB släpper ny version, eller om någon behöver verifiera att
JSON:en stämmer mot källan:

```powershell
# 1. Ladda ner originalfilen från https://www.scb.se/sni och lägg
#    den lokalt (gitignored automatiskt):
copy ~\Downloads\SNI-2025.xlsx data\taxonomies\sni\sni-2025.source.xlsx

# 2. Kör extractor:
python scripts\extract_sni_2025.py `
  --source data\taxonomies\sni\sni-2025.source.xlsx `
  --out data\taxonomies\sni\sni-2025.v1.json

# 3. Verifiera mot committad version (extractor jämför default-paths):
python scripts\extract_sni_2025.py --check

# 4. Radera Excel-källan (canonical lever i JSON):
del data\taxonomies\sni\sni-2025.source.xlsx
```

Om din lokala fil heter annat än default-namnet, ange `--source` med
det faktiska filnamnet — gitignore-mönstret matchar alla `*.xlsx`
under `data/taxonomies/`.

## Sök i taxonomin

```powershell
python scripts\lookup_sni.py code 56110            # uppslagning + parent-chain
python scripts\lookup_sni.py text "frisör"         # fritext i labelSv (case-insensitive)
python scripts\lookup_sni.py section I             # avdelning I (hotell/restaurang)
python scripts\lookup_sni.py level group           # alla 287 grupper
python scripts\lookup_sni.py stats                 # antal per nivå
```

Alla subkommandon accepterar `--json` för strukturerad output (agent-
konsumtion), `--limit N` för att cappa antal träffar (default 50), och
`--file PATH` för att override:a JSON-källan. Flaggorna kan placeras
före eller efter subkommandot. Sökningen i `text` är case-insensitive
men foldar **inte** diakritiska tecken; sök efter `frisör` (inte
`frisor`) för att träffa svensk text.

## Konsumtion i kod

| Konsument | Läser | Beskrivning |
|-----------|-------|-------------|
| [`packages/generation/discovery/sni_map.py`](../../../packages/generation/discovery/sni_map.py) | [`governance/policies/sni-discovery-map.v1.json`](../../../governance/policies/sni-discovery-map.v1.json) | Resolver-helper: SNI-kod -> wizardCategoryId |
| [`backoffice/sni_diagnostics.py`](../../../backoffice/sni_diagnostics.py) | Båda policyn + JSON-spegeln | Read-only Backoffice-diagnostik |
| [`scripts/lookup_sni.py`](../../../scripts/lookup_sni.py) | JSON-spegeln | CLI-sök (denna mapp) |

`sni_map.py` läser **policyn**, inte JSON-spegeln direkt. JSON:en är
reference data; policyn är operatörens handstyrda mappning till
wizardkategorier. Se policyns `principles[]` för reglerna kring varför
SNI aldrig får sätta `starterId`, `scaffoldId`, `variantId` eller
Dossier direkt.

## V1-begränsningar

- Ingen runtime-konsumtion av SNI sker än. Viewser-overlay, `/api/prompt`,
  planning och codegen är oförändrade.
- 21 huvudgrupp-mappningar + 18 grupp-overrides i policyn täcker en
  delmängd av taxonomin; resten faller till `unknown` utan exception.
- Inga 4- eller 5-siffriga overrides i policyn V1 — om Detaljhandel
  (47) eller liknande behöver finkornigare mappning kan policyn bumpas
  till v2 utan att JSON-spegeln rörs.
