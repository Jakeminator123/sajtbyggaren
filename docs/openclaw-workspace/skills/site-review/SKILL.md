# SKILL: site_review

## Mål
Svara på frågor om sajten eller föreslå förbättringar UTAN att bygga om, t.ex.
"vad tycker du om sidan?" eller "vad kan förbättras?".

## Väg
router (site_review / answer_only) -> läs artefakter (brief/plan/run) ->
svara/föreslå. Ingen patch, ingen build, ingen preview-refresh.

## Gränser
Read-only. Föreslår block-ändringar (restyle/copy/section_add) som operatören
sedan kan be om — utför dem aldrig själv i detta skill.

## Status
partial (svar finns; strukturerade förbättringsförslag är en framtida breddning).
