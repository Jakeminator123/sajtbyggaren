# ADR 0002: Backoffice som `backend.py` Streamlit, separat från runtime

- Status: accepterat
- Datum: 2026-05-07

## Kontext

I sajtmaskin fanns en omfattande Streamlit-baserad backoffice (`backoffice/`, `sajtmaskin_backoffice.py`) som blandade översikt, redigering, evals och telemetri. Den fungerade som översikt men växte ihop med runtime via gemensamma moduler.

Användaren vill behålla **idén** med en Streamlit-backoffice för att överblicka och redigera scaffolds, dossiers, policies, fas 1-3 i LLM-flödet, evals och telemetri, men hålla den **fullständigt separerad från användarens runtime-flöde**.

## Beslut

- Sajtbyggaren har en enda backoffice-startpunkt: `backend.py` i repo-roten (Streamlit-app).
- Backoffice får läsa och redigera filer under `governance/`, `data/` och scripts under `scripts/`.
- Backoffice får INTE ingå i användarens runtime-flöde. Den får inte exponera generation-API:er åt slutanvändare, och får inte importera ut från `apps/`-laddade moduler.
- Den användarvända produkten (när tiden är inne) byggs i `apps/web/` (UI) + `apps/api/` (HTTP) som konsumerar `packages/`.
- Naming-dictionary listar `Backoffice` som kanonisk term med `ownerPackage: backend.py`.

## Konsekvenser

- Tydlig mental separation: en knapptryckning i Streamlit förändrar inte vad slutanvändaren ser i realtid om det inte också skrivs till en policy som runtime läser.
- Backoffice får en växande yta: överblick + redigering av policies, scaffolds, dossiers, fasvisning, evals, telemetri. Den ska byggas inkrementellt, inte all-at-once.
- Streamlit ger snabb iteration och passar för administrativa ytor; produktens UI byggs separat med Next.js-likt stack om det visar sig nödvändigt.
