# Code Owner Proposal

Skapa inte en skarp code owner-konfiguration innan frontend-medutvecklarens
GitHub-username är känd. Den här filen är bara ett förslag.

När frontend-medutvecklarens GitHub username är känd kan en framtida PR lägga
till något i den här stilen:

```text
/packages/generation/        @Jakeminator123
/governance/                 @Jakeminator123
/data/starters/              @Jakeminator123
/apps/viewser/               @FRONTEND_USERNAME
/docs/contracts/             @Jakeminator123 @FRONTEND_USERNAME
```

Innan detta blir skarp config:

- Byt `@FRONTEND_USERNAME` mot rätt GitHub-username.
- Kontrollera att GitHub-team eller användare har repo-access.
- Håll reviewkrav smala så docs inte blockerar produktflödet i onödan.
