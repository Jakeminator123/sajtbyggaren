# delivery-bias

det här är en liten styrning för agentarbete när scope riskerar att glida
från leverans till kartläggning, dokumentation eller testlager.

## grundprincip

förmåga före dokumentation. en doc-only-pr är rätt bara när den tar bort
oklarhet som faktiskt blockerar bygge eller review av bygge.

## testbudget

lägg till test när det gör minst en av dessa saker:

- skyddar ett nytt kontrakt
- ersätter ett äldre test
- konsoliderar flera test till ett tydligare skydd

breda regressionstest är inte standard. välj det smalaste testet som bevisar
ändringen och skriv varför just det testet behövs.

## agentroller

- builder levererar en smal runtime-effekt.
- scout hittar glapp, inte stora kartor.
- steward minskar oreda och håller nästa agent ospärrad.
- cloud får städa tester, men lägger inte ett nytt testlager utan en konkret
  deletion- eller merge-plan.

## feature-pr

en feature-pr ska redovisa:

- vilken användarsynlig förmåga som blev bättre
- vilka hot-filer som ändrades
- vilka test som lades till och varför
- vilka test som kunde undvikas och varför
- om build context måste laddas om
