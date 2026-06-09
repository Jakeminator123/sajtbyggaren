---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

> **Arkivnot (lane A, 2026-06):** Pausad referens. StackBlitz-runtimen är pausad
> (ADR 0033); dagens preview-väg beskrivs i
> [`docs/architecture/preview-runtime.md`](../architecture/preview-runtime.md).
> Behålls *på plats* (länkas från architecture-docs). Se `docs/archive/README.md`.

# StackBlitz research for an AI-powered code editing product

> **Status:** extern research, inte beslut. Materialet är insamlat 2026-05-18
> som underlag för framtida arbete på `StackBlitzRuntime`
> (`packages/preview-runtime/stackblitz/`) och dess host-frontend. Alla
> arkitekturbeslut sker fortfarande via ADR i `governance/decisions/` och
> styrs av `preview-runtime-policy.v1.json`.
>
> Konkreta implementationsnoteringar (boot/mount/spawn/server-ready,
> COOP/COEP-headers, vanliga fel) lever i
> [`webcontainers-notes.md`](webcontainers-notes.md). Den här filen är
> bredare och täcker även SDK-, Codeflow-, Teams- och MCP-ytan plus
> licens-/browser-begränsningar som påverkar host-valet.
>
> Citerade StackBlitz-/web-produktnamn (`WebContainer API`,
> `EngineBlock`, `CodeflowApp`, `WebAssembly`, m.fl.) är externa
> bibliotekstermer, inte sajtbyggaren-domänbegrepp - de är därför
> allowlistade i `scripts/check_term_coverage.py` enligt samma mönster
> som `StackBlitz`/`WebContainer`/`OpenAI`.

## Bottom line

If your real goal is: **"users on my future site can prompt, inspect, edit, run, and preview code effectively"**, the most relevant StackBlitz layer is not mainly Codeflow or Teams. It is the **WebContainer API** (browser runtime) plus, secondarily, the **StackBlitz JavaScript SDK** (software kit) for fast embeds and "open in StackBlitz" flows.

StackBlitz positions its SDK as a way to programmatically create and embed StackBlitz projects, while WebContainers positions its public API as the foundation for AI applications, browser IDEs, tutorials, and adding in-browser code execution to an existing product.

That distinction matters because StackBlitz embeds are the fastest way to prototype, but WebContainers are the stronger foundation for a real product UI where your app controls files, commands, previews, and agent actions. The API exposes filesystem operations, command execution, lifecycle control, and server-readiness events. That is much closer to what an AI coding workflow needs than a generic embedded editor iframe.

The biggest non-obvious constraint is that WebContainers are browser-native infrastructure, not cloud VMs. That reduces server-side execution burden, but it pushes product risk into browser requirements:

- cross-origin isolation headers
- service workers across several domains
- storage/cookie restrictions
- an official support baseline that is strongest in Chromium-based browsers

Also, StackBlitz says commercial production use of the WebContainer API requires a commercial license, which is critical if this is for a future for-profit site.

I also checked the **MCP** (tool protocol) angle. I did not find an official StackBlitz MCP server in the official StackBlitz/WebContainers docs I reviewed. What I did find is a third-party `stackblitz-mcp` project for reading StackBlitz project metadata and files.

By contrast, Vercel now has an official MCP server and first-class docs for deploying your own MCP servers, which is the clearest reason Vercel may have shown up in the earlier research plan.

## What StackBlitz actually offers

| Surface | Best fit | Why it matters |
|---|---:|---|
| **JS SDK + embedded editor** | Fast prototype | Lets you create, open, and embed StackBlitz projects programmatically, then control the embedded VM (runtime) to switch files and read/write the virtual filesystem. Good for docs, playgrounds, and guided examples. |
| **WebContainer API** | Core product runtime | Headless browser-based Node.js runtime for custom UIs. Suitable for AI apps, in-browser code execution, IDEs, tutorials, and "code inside my own product." |
| **Codeflow + `pr.new`** | GitHub-centric workflow | One-click GitHub integration for repos, branches, PR review, and single-file/docs editing through Web Publisher. Excellent for repo workflows, less ideal as the main public-site runtime. |
| **Teams** | Internal/private org use | Private workspace tied 1:1 to a GitHub Organization, inherits GitHub repo permissions, supports private registries, and stores per-user environment variables. |

Under the hood, StackBlitz has two compute environments:

1. **EngineBlock** - front-end oriented, older, easier for simple embeds.
2. **WebContainers** - full Node.js, terminal, full-stack capable.

StackBlitz says Codeflow and Web Publisher are WebContainers-only, while the classic editor can sit on either environment depending on project type. For most present and future workloads, StackBlitz recommends WebContainers.

A useful caution: the docs are not equally fresh. The WebContainers roadmap explicitly says it may contain outdated information, the browser-support page still carries a February 2023 update marker, and the Codeflow FAQ still contains clearly beta-era language.

So for architecture decisions, newer pages like the WebContainer API, AI, commercial-use, SDK, and Vercel MCP docs are more trustworthy than older roadmap/FAQ pages.

## Best integration path for your site

If you want your own UX where a user writes a prompt, an agent edits files, commands run, and a preview updates inside your page, the strongest official path is the **WebContainer API**.

It lets you:

- `mount` - load files
- `fs.writeFile` - edit files
- `fs.readFile` - read files
- `spawn` - run commands
- subscribe to `server-ready` - preview-ready event
- `teardown` - dispose runtime

That is the low-level product surface you need for AI-assisted coding.

If you want the fastest proof of concept, use the **StackBlitz JS SDK**. The SDK can embed or open projects, and once embedded, the VM interface can control the UI and read/write project files.

The options system also lets you set:

- `openFile` - which file opens
- highlighted lines or ranges
- `clickToLoad` - lazy loading
- terminal/devtools size

That is very good for examples, tutorials, and guided coding flows.

There is also a no-JavaScript fallback: StackBlitz documents a POST API that creates projects by posting project data from a form. That is useful if your environment cannot or should not use the JavaScript SDK, but it is more limited and explicitly does not support binary files in dynamically created projects.

For repo-based workflows, StackBlitz's GitHub path is separate from the embed path. The `pr.new` shortcut can open a repo, branch, pull request, or single file in Codeflow or Web Publisher, and CodeflowApp can pre-clone default-branch and PR commits for faster startup. That is ideal when the end state is a GitHub contribution flow rather than a browser-only sandbox.

One subtle but important detail: StackBlitz says SDK-created projects with `template: 'node'` use WebContainers, and that path is currently on `stackblitz.com` only. Other templates can use EngineBlock instead.

So if your long-term goal is a bespoke runtime primarily living inside your own product rather than an embedded StackBlitz surface, the WebContainer API is the more future-proof route.

A small but genuinely useful advanced setting for AI workflows is `compileTrigger` (when edits sync). StackBlitz documents `auto`, `keystroke`, and `save`, and explicitly notes that `save` can reduce errors when compilers/dev servers are not resilient to temporarily invalid code while a user is typing.

That is directly relevant if an agent applies multi-step file edits. The same project config surface also supports:

- `startCommand` - startup command
- `installDependencies` - dependency installation
- default env values through `package.json` or `.stackblitzrc`

## Constraints you need to design around

For a deployed WebContainer app, the big requirement is **cross-origin isolation**.

The official tutorial says WebContainers only run when the document is served with:

```http
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Opener-Policy: same-origin
```

It also explicitly notes that while `localhost` gets some exemptions, there is no way around this in production.

This is one reason Vercel is relevant even if StackBlitz is your runtime vendor. Vercel's `vercel.json` supports route-based custom response headers, so it is a practical place to set the COOP/COEP isolation headers needed by a WebContainer host app.

Browser support is the next hard boundary. StackBlitz says WebContainers are fully supported in Chrome and other Chromium-based browsers, but Firefox and Safari are still beta with preview limitations tied to cross-origin isolation behavior.

More importantly for your use case, StackBlitz explicitly says embedded WebContainers-based projects are only officially supported in Chromium-based browsers. If your future site depends on embedded StackBlitz/WebContainers, Chrome/Edge/Brave should be treated as the main supported baseline.

The runtime also depends on Service Workers and WebAssembly across multiple domains, which means privacy settings can break it. Chrome may need storage partitioning or exceptions for StackBlitz/WebContainer domains, and Brave blocks cross-site cookies and service workers aggressively by default unless users allow them. StackBlitz even documents popup exceptions for separate-tab previews.

Finally, compatibility is strong but not universal. StackBlitz's troubleshooting docs say native addons are disabled unless they can be compiled to WebAssembly, so packages that rely on native C/C++ addons can fail.

In practice, that means validating your actual framework, bundler, test runner, and package set before you commit to the architecture.

## MCP status and why Vercel matters

From the official StackBlitz side, the documented integration surfaces I found are:

- JavaScript SDK
- SDK VM controls
- POST API
- WebContainer API
- Codeflow
- Web Publisher
- CodeflowApp
- Teams

I did not find an official StackBlitz MCP page among those official docs. That does not prove no internal or future MCP work exists, but it does mean MCP is not currently presented as a first-class public integration surface the way SDKs and WebContainers are.

What I did find is a third-party project, `stackblitz-mcp`, on GitHub. Its published tools include:

- `resolve_project`
- `list_files`
- `read_file`
- `search_files`

Its README includes example Cursor configuration using:

```bash
npx -y stackblitz-mcp
```

That can make a Cursor-style agent better at inspecting StackBlitz projects, but the documented toolset is read-oriented. It is not an official StackBlitz write/run/deploy control layer.

Vercel is much stronger on MCP right now. Vercel documents an official MCP server, lists support for clients including Cursor, ChatGPT, and Codex CLI, and says its MCP tools can search docs and manage projects, deployments, and logs.

Vercel also documents how to deploy your own MCP servers on its platform and exposes CLI support for connecting local MCP clients to servers deployed on Vercel.

So the likely reason Vercel showed up is this: **StackBlitz/WebContainers solves the browser-side runtime, while Vercel can solve the cloud-side control plane.**

In other words, one plausible architecture is:

> Run untrusted code in the user's browser via WebContainers, but expose repo/deployment/product actions through your own MCP server on Vercel.

That separation is cleaner than trying to make StackBlitz itself be the MCP host.

There is one more Vercel reason: Git pushes and pull requests automatically get preview deployments, which pairs naturally with a workflow where browser-generated code eventually becomes a repo branch or PR.

If your product ever moves from ephemeral browser sandbox to deployable Git-backed output, that preview model is useful.

## Recommended architecture

| Recommendation | Fit | Notes |
|---|---:|---|
| **WebContainer API as the core runtime** | **90%** | Best match for a public-facing product where users prompt an agent, inspect files, run commands, and preview output without leaving your site. It is explicitly positioned for AI apps and existing products, gives you the right file/process primitives, and keeps untrusted execution inside the browser instead of your cloud. Do not forget the commercial-license requirement for production use. |
| **StackBlitz JS SDK as the fastest prototype** | **75%** | Use it to validate UX quickly, create interactive docs/examples, or provide a fallback "open in full StackBlitz editor" path. Probably the shortest road to something real, but still more embed-centric than product-core. |
| **Codeflow and `pr.new` as a GitHub escape hatch** | **65%** | Useful if your product eventually needs a "continue this in a full IDE" or "open this repo/PR/docs edit" flow. Treat it as an extension path, not the primary runtime for anonymous/public users. |
| **Teams as an internal/admin workflow** | **40%** | Good if you or enterprise customers need a private GitHub-org workspace with mirrored permissions, private registries, and secure per-user env vars. Not the obvious base layer for a public consumer-facing coding surface. |

## Implementation sequence

1. Build the browser runtime around WebContainer API and host the app somewhere that can set the required isolation headers cleanly, such as Vercel.
2. Add JS SDK embeds or "open in StackBlitz" flows as a fallback or onboarding path.
3. If GitHub is part of the workflow, add `pr.new` and optionally CodeflowApp.
4. If you want agent tooling, put MCP on your side, likely on Vercel, and use community StackBlitz MCP only as an optional read-helper for project inspection. Also keep Vercel's human-confirmation guidance if tools can change repos or deployments.
5. Before launch, resolve WebContainer API commercial licensing with StackBlitz.

## Confidence

My confidence is **high** on the main product boundaries:

- WebContainers as the correct technical substrate for in-browser AI coding
- the need for COOP/COEP headers
- the Chromium-first embed reality
- the commercial-license requirement for production WebContainer use
- Vercel's official MCP support

Those points are all directly documented in current primary sources.

My confidence is **medium** on the broader StackBlitz MCP landscape, because the official StackBlitz docs I reviewed do not surface MCP as a first-class public integration, while the only concrete StackBlitz MCP path I found was a community GitHub project.

There is also some visible staleness in older StackBlitz pages, so I would re-check any older FAQ or roadmap detail before treating it as current product truth.

## Sources

- [JavaScript SDK | StackBlitz Docs](https://developer.stackblitz.com/platform/api/javascript-sdk)
- [API Reference | WebContainers](https://webcontainers.io/api)
- [Setting up WebContainers | WebContainers](https://webcontainers.io/tutorial/2-setting-up-webcontainers)
- [WebContainer API | StackBlitz Docs](https://developer.stackblitz.com/platform/api/webcontainer-api)
- [What is Codeflow? | StackBlitz Docs](https://developer.stackblitz.com/codeflow/what-is-codeflow)
- [Managing your Team | StackBlitz Docs](https://developer.stackblitz.com/teams/setting-up-your-team)
- [Available environments | StackBlitz Docs](https://developer.stackblitz.com/guides/user-guide/available-environments)
- [Roadmap | StackBlitz Docs](https://developer.stackblitz.com/platform/webcontainers/roadmap)
- [POST API | StackBlitz Docs](https://developer.stackblitz.com/platform/api/post-api)
- [Using pr.new | StackBlitz Docs](https://developer.stackblitz.com/codeflow/using-pr-new)
- [Managing dependencies with the SDK | StackBlitz Docs](https://developer.stackblitz.com/platform/api/javascript-sdk-dependencies)
- [Project configuration | StackBlitz Docs](https://developer.stackblitz.com/platform/webcontainers/project-config)
- [Static Configuration with vercel.json](https://vercel.com/docs/project-configuration/vercel-json)
- [WebContainers Browser Support | StackBlitz Docs](https://developer.stackblitz.com/platform/webcontainers/browser-support)
- [Configuring your browser to run WebContainers | StackBlitz Docs](https://developer.stackblitz.com/platform/webcontainers/browser-config)
- [Troubleshooting WebContainers | StackBlitz Docs](https://developer.stackblitz.com/platform/webcontainers/troubleshooting-webcontainers)
- [GitHub - sxzz/stackblitz-mcp](https://github.com/sxzz/stackblitz-mcp)
- [Use Vercel's MCP server](https://vercel.com/docs/agent-resources/vercel-mcp)
- [Introduction | WebContainers](https://webcontainers.io/guides/introduction)
- [Deploying GitHub Projects with Vercel](https://vercel.com/docs/git/vercel-for-github)
- [In-browser code execution for AI | WebContainers](https://webcontainers.io/ai)
- [Commercial Usage | WebContainers](https://webcontainers.io/enterprise)
