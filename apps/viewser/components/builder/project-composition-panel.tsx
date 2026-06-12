"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Projektinnehåll-panelen: visar vad sajt-projektet faktiskt består av —
 * sidor, funktioner (dossiers), komponenter och npm-paket — med en tydlig
 * "vad kan jag ändra?"-vinkel:
 *
 *   - Sidor och texter ändras via följdprompt i chatten.
 *   - Funktioner (dossiers) väljs av plannern; operatören kan be om fler.
 *   - Paket är operatörskuraterade (ADR 0056) och ändras INTE via prompt —
 *     de visas för transparens, med dossier-attribution för tillagda paket.
 *
 * Data kommer från GET /api/site/<siteId>/composition som DERIVERAR bilden
 * ur befintliga källor (senaste runens artefakter + genererad package.json/
 * component-manifest + project-input) — se lib/site-composition.ts. Alla
 * fält är defensivt nullbara; saknade källor renderas som ärliga
 * "okänt"-rader i stället för gissningar. Hostat kan svaret bära en
 * ``hostedNotice`` (B199-degradering) som visas som lugn info, inte fel.
 *
 * Designspråket speglar RunDetailsPanel (kort + text-xs + mono-värden) så
 * panelen smälter in i ConsoleDrawer.
 */

type CompositionPayload = {
  siteId: string;
  version: number | null;
  scaffoldId: string | null;
  variantId: string | null;
  starterId: string | null;
  language: string | null;
  companyName: string | null;
  routes: Array<{ id: string | null; path: string }> | null;
  dossiers: Array<{
    id: string;
    status: "required" | "recommended" | "conditional" | "rejected";
    reason: string | null;
  }> | null;
  components: string[] | null;
  dependencies: {
    base: Record<string, string>;
    added: Array<{ name: string; version: string; source: string | null }>;
  } | null;
  lastBuild: { runId: string; status: string; createdAt: string | null } | null;
  hostedNotice?: string;
};

const DOSSIER_STATUS_LABEL: Record<string, string> = {
  required: "monterad",
  recommended: "rekommenderad",
  conditional: "villkorad",
  rejected: "avvisad",
};

function statusToneClass(status: string): string {
  if (status === "ok" || status === "required") {
    return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30";
  }
  if (status === "degraded" || status === "recommended" || status === "conditional") {
    return "bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/30";
  }
  if (status === "failed" || status === "aborted" || status === "rejected") {
    return "bg-destructive/15 text-destructive border-destructive/30";
  }
  return "bg-muted text-muted-foreground border-border";
}

function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <Badge
      variant="outline"
      className={`font-mono text-[10px] ${statusToneClass(status)}`}
    >
      {label ?? status}
    </Badge>
  );
}

function SectionBlock({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <p className="text-xs font-medium text-foreground">{title}</p>
        {hint ? (
          <p className="text-[10.5px] text-muted-foreground">{hint}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function UnknownNote({ label }: { label: string }) {
  return <p className="text-xs italic text-muted-foreground">{label}</p>;
}

export function ProjectCompositionPanel({ siteId }: { siteId: string | null }) {
  const [data, setData] = useState<CompositionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showBaseDeps, setShowBaseDeps] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // setState efter await (async IIFE) — samma mönster som
    // RunDetailsPanel för React 19:s react-hooks/set-state-in-effect.
    void (async () => {
      if (!siteId) {
        if (cancelled) return;
        setData(null);
        setError(null);
        setLoading(false);
        return;
      }
      if (cancelled) return;
      setData(null);
      setError(null);
      setLoading(true);
      try {
        const response = await fetch(
          `/api/site/${encodeURIComponent(siteId)}/composition`,
        );
        const payload = (await response.json()) as CompositionPayload & {
          error?: string;
        };
        if (!response.ok || payload.error) {
          throw new Error(
            payload.error ?? "Kunde inte hämta projektinnehållet.",
          );
        }
        if (!cancelled) setData(payload);
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Okänt fel.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [siteId]);

  const baseDeps = data?.dependencies ? Object.entries(data.dependencies.base) : [];
  const addedDeps = data?.dependencies?.added ?? [];

  return (
    <Card data-testid="project-composition-panel">
      <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border/60 pb-3">
        <CardTitle className="text-base">Projektinnehåll</CardTitle>
        {siteId ? (
          <Badge variant="outline" className="font-mono text-[10px]">
            {siteId.length > 26 ? `${siteId.slice(0, 26)}…` : siteId}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 pt-4 text-xs">
        {!siteId ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
            Välj en sajt eller bygg en ny så visas vad projektet består av.
          </div>
        ) : null}

        {loading ? (
          <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="flex flex-col gap-2"
          >
            <span className="sr-only">Laddar projektinnehåll…</span>
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-16 w-full rounded-md" />
          </div>
        ) : null}

        {error ? (
          <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            {error}
          </p>
        ) : null}

        {data?.hostedNotice ? (
          // Medveten hostad degradering — lugn info-ruta, inte fel-röd.
          <p
            role="status"
            className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground"
          >
            {data.hostedNotice}
          </p>
        ) : null}

        {data ? (
          <>
            {/* Översikt: företag, scaffold/variant, språk, version, bygge. */}
            <div className="space-y-1 rounded-lg border border-border/60 bg-background/40 p-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  {data.companyName ?? "Företagsnamn okänt"}
                </p>
                {data.lastBuild ? (
                  <StatusBadge status={data.lastBuild.status} />
                ) : null}
              </div>
              <p className="text-muted-foreground">
                {data.version !== null ? `Version ${data.version}` : "Version okänd"}
                {" · "}scaffold:{" "}
                <span className="font-mono">{data.scaffoldId ?? "okänd"}</span>
                {" · "}variant:{" "}
                <span className="font-mono">{data.variantId ?? "okänd"}</span>
                {" · "}språk:{" "}
                <span className="font-mono">{data.language ?? "okänt"}</span>
              </p>
              <p className="text-[10.5px] text-muted-foreground">
                Texter, färger och innehåll ändrar du med en följdprompt i
                chatten.
              </p>
            </div>

            <SectionBlock
              title="Sidor"
              hint="Redigerbara — be om en ny sida i en följdprompt."
            >
              {data.routes && data.routes.length > 0 ? (
                <ul className="space-y-0.5">
                  {data.routes.map((route) => (
                    <li key={route.path} className="flex items-baseline gap-2">
                      <span className="font-mono">{route.path}</span>
                      {route.id ? (
                        <span className="text-muted-foreground">{route.id}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <UnknownNote label="Sidor okända — site-plan saknas för senaste bygget." />
              )}
            </SectionBlock>

            <SectionBlock
              title="Funktioner (dossiers)"
              hint="Väljs av plannern — be om fler i en följdprompt."
            >
              {data.dossiers && data.dossiers.length > 0 ? (
                <ul className="space-y-1">
                  {data.dossiers.map((dossier) => (
                    <li
                      key={`${dossier.status}-${dossier.id}`}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <span className="font-mono">{dossier.id}</span>
                      <StatusBadge
                        status={dossier.status}
                        label={DOSSIER_STATUS_LABEL[dossier.status] ?? dossier.status}
                      />
                      {dossier.reason ? (
                        <span className="text-[10.5px] text-muted-foreground">
                          {dossier.reason}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : data.dossiers ? (
                <p className="text-muted-foreground">
                  Inga extra funktioner valda för det här bygget.
                </p>
              ) : (
                <UnknownNote label="Dossier-urval okänt — site-plan saknas för senaste bygget." />
              )}
            </SectionBlock>

            <SectionBlock title="Komponenter">
              {data.components && data.components.length > 0 ? (
                <p className="font-mono text-muted-foreground">
                  {data.components.join(" · ")}
                </p>
              ) : data.components ? (
                <p className="text-muted-foreground">
                  Inga UI-komponenter listade i manifestet.
                </p>
              ) : (
                <UnknownNote label="Komponenter okända — component-manifest saknas." />
              )}
            </SectionBlock>

            <SectionBlock
              title="Paket"
              hint="Operatörskuraterade — ändras inte via prompt."
            >
              {data.dependencies ? (
                <div className="space-y-1.5">
                  {addedDeps.length > 0 ? (
                    <div data-testid="composition-added-packages">
                      <p className="text-muted-foreground">
                        Tillagda paket (via dossiers):
                      </p>
                      <ul className="ml-4 list-disc">
                        {addedDeps.map((dep) => (
                          <li key={dep.name}>
                            <span className="font-mono">
                              {dep.name}@{dep.version}
                            </span>
                            <span className="text-muted-foreground">
                              {dep.source
                                ? ` — från dossier ${dep.source}`
                                : " — käll-dossier okänd"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">
                      Inga dossier-tillagda paket — allt kommer från starterns
                      baspaket.
                    </p>
                  )}
                  <button
                    type="button"
                    className="text-[10.5px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                    onClick={() => setShowBaseDeps((prev) => !prev)}
                    aria-expanded={showBaseDeps}
                  >
                    {showBaseDeps
                      ? "Dölj baspaket"
                      : `Visa baspaket (${baseDeps.length})`}
                  </button>
                  {showBaseDeps ? (
                    <ul className="ml-4 list-disc font-mono text-muted-foreground">
                      {baseDeps.map(([name, version]) => (
                        <li key={name}>
                          {name}@{version}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : (
                <UnknownNote label="Paket okända — genererad package.json kunde inte läsas." />
              )}
            </SectionBlock>

            {data.lastBuild ? (
              <p className="border-t border-border/60 pt-2 text-[10.5px] text-muted-foreground">
                Senaste bygge:{" "}
                <span className="font-mono">
                  {data.lastBuild.runId.length > 30
                    ? `${data.lastBuild.runId.slice(0, 30)}…`
                    : data.lastBuild.runId}
                </span>
                {data.lastBuild.createdAt
                  ? ` · ${new Date(data.lastBuild.createdAt).toLocaleString("sv-SE")}`
                  : null}
              </p>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
