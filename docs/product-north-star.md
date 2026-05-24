# Produktnordstjärna

Sajtbyggaren bygger bättre företagshemsidor för småföretagare.

Kärnflödet är:

```text
prompt -> hemsida -> preview -> följdprompt -> ny version
```

Allt agentarbete ska prövas mot om det gör kärnflödet stabilare, tydligare
eller bättre för småföretagaren.

## Riktning

- Lovable/v0 är kvalitetsribba för enkelhet, iteration och finish, inte
  arkitekturmall.
- Gamla Sajtmaskin är referens och baslinje, inte kodbas att återinföra.
- Governance ska skydda riktningen, inte kväva bygget.
- Välj liten sammanhängande kärna före bred plattformsbredd.

## Vänta med

Vänta med auth, billing, Stripe, Supabase, Shopify, custom domain, avancerad
deploy, marketplace och stora integrationslager tills kärnflödet är stabilt.

Om en uppgift inte hjälper `prompt -> hemsida -> preview -> följdprompt -> ny
version` ska den normalt parkeras.
