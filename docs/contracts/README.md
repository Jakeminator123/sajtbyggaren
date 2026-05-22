# Contracts

Shared contracts är gränsen mellan frontend och backend. Ett contract beskriver
datamodellen, inte vem som råkar ha implementerat den först.

Contract-first betyder:

1. Skriv type/interface eller motsvarande shape.
2. Lägg till mock JSON som frontend kan bygga mot.
3. Beskriv success, error och loading.
4. Sätt ägare och reviewer.
5. Lägg till en testidé innan implementationen växer.

Om backend saknas får frontend använda mockar. Om frontend saknas får backend
ändå låsa output-shape med exempel och tester. Ingen sida ska behöva gissa
fält eller statusvärden.

## Exempel på datamodell

```ts
type Run = {
  id: string
  projectId: string
  version: number
  status: "queued" | "running" | "ready" | "failed"
  previewUrl?: string
  errorMessage?: string
  createdAt: string
}
```

Här betyder `type` datamodell/shape för frontend-backend-gränsen. Det är
dokumentation tills repo:t har en beslutad plats för delade TypeScript-typer.

## States varje contract bör visa

- Success: komplett data som UI:t kan rendera.
- Loading: minsta state medan backend jobbar.
- Error: vad frontend får visa utan att läsa interna loggar.
- Empty: om listor eller val kan vara tomma.

## Namngivning

- Ett contract får versionssuffix: `generation-run.v1`.
- Breaking change kräver ny version eller tydlig migrationsnotis.
- Mockar ska ligga nära dokumentet eller i en beslutad mock-yta när den finns.

## Startpunkter

- `docs/contracts/generation-run.v1.md` är första konkreta contract.
- Framtida kandidater: `preview-state.v1` och `followup-version.v1`.
