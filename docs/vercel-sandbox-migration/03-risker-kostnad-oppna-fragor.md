# Risker, kostnad och öppna frågor

## Risker
- Sandbox-kostnad kan skena om previews inte idle-stoppas eller ttl-städas. Varje
  sandbox kostar cpu och nätverk; en warm-pool kostar även när ingen tittar. Mät tidigt.
- Kallstart utan snapshots gör v0- eller Lovable-känslan svår (~30 s). Snapshots är
  en förutsättning, inte en lyx-optimering.
- Python i sandbox kan ha tunga beroenden (modell-anrop, paket). Verifiera att hela
  pipen kör i node24-runtimen, annars behövs en egen container eller worker.
- Multi-tenant-läckage: utan tenant-scoping kan en användare nå en annans sandbox
  eller preview. Auth och scoping är säkerhetskritiskt, inte kosmetiskt.
- Localhost-låset finns av en anledning (routerna spawnar processer och sandboxar);
  att öppna det hostat utan auth vore en öppen relä för kostsam körning.
- Beständighet: lokal disk -> blob och databas är en bred refaktor; risk för
  regressioner i lokal utveckling om inte fallback-läget hålls grönt.

## Kostnadsskisser (att verifiera, inte sanning)
- Preview-sandbox: `npm install` plus `next build` plus `next start` per kallstart.
  En snapshot tar bort install och återanvänder beroenden. En warm-pool = N
  alltid-på sandboxar.
- Bygg-sandbox: en körning per prompt eller följdprompt. Slå ihop bygg och preview
  om möjligt.
- Blob-lagring plus databas: löpande men billigt jämfört med compute.

## Öppna frågor
- Ska bygg och preview vara samma sandbox eller två? (G1 A mot B.)
- Vilken databas eller nyckel-värde-lagring? (Marketplace-Postgres mot Redis mot
  Edge Config för bara pekaren.)
- Vilken auth-leverantör? (Clerk native mot Descope mot Auth0 — se auth-skillen.)
- Hur länge ska en preview leva? Per session mot en delbar länk med längre ttl?
- Behåller vi Python på sikt, eller portar vi byggaren till Node (G1 C)?
- Hur hanteras hemligheter (modell-nyckeln) i bygg-sandboxen utan att de läcker?
