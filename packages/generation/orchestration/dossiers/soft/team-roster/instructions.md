# when to use

Use this dossier when the brief or a follow-up implies the site should present
the people behind the business: a "vårt team", "personal", "medarbetare" or
"om oss"-team block. Triggers include `team`, `teamet`, `personal`,
`medarbetare`, `anställda`, `staff`.

Best fit:

- An about-page team grid of named people with their roles.
- A short "vårt team"-strip on the home page once the operator supplies names.

Do not use for:

- A single solo operator with no named colleagues - one person is the founder
  story, not a team grid.
- Inventing people. The section is data-driven: with no `company.team` entries
  it renders nothing rather than fabricating staff.

# how to integrate

The deterministic builder already renders this section via the existing
`render_section_team` helper, driven by the `company.team` array in the
project-input (each entry is a `name` + `role`). Mounting this dossier marks the
team capability as selected so the section is treated as part of the site; it
adds no new component and no new render path.

Contract points the rendered section keeps:

1. one card per `company.team` entry, with a monogram initial, the member name
   and the member role - semantic list markup, no client JS.
2. an empty or missing `company.team` renders nothing (no empty heading, no
   placeholder people) - honesty over filler.
3. roles stay short and concrete (the operator's own wording), never invented
   titles.

# forbidden anti-patterns

- Generating fake team members or stock-photo avatars to fill the grid.
- Turning a one-person business into a multi-person team.
- Duplicating the founder story as a team card.
