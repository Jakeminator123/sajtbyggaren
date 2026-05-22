"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export type ProjectInputOption = {
  siteId: string;
  companyName: string;
  scaffoldId: string;
  variantId: string;
  language: string;
  source: "examples" | "prompt-inputs";
};

type ProjectInputPickerProps = {
  inputs: ProjectInputOption[];
  selectedSiteId: string;
  onSelect: (siteId: string) => void;
  /**
   * siteId från vald run i Run History. När detta matchar
   * `selectedSiteId` visar vi en "Följer vald run"-badge så det blir
   * tydligt varför picker:n bytte. När runens siteId saknas i
   * `inputs`-listan visar vi en varning: panelen kunde inte hitta
   * matchande Project Input på disk (t.ex. för exempel-runs eller
   * gamla runs där prompt-input-snapshoten städats).
   */
  runSiteId: string | null;
  /** Vald run finns men siteId är "unknown" / saknas — follow-up är osäker. */
  runSiteIdUnknown?: boolean;
};

export function ProjectInputPicker({
  inputs,
  selectedSiteId,
  onSelect,
  runSiteId,
  runSiteIdUnknown = false,
}: ProjectInputPickerProps) {
  const selected = inputs.find((input) => input.siteId === selectedSiteId);
  const followsRun = !!runSiteId && runSiteId === selectedSiteId;
  const runMissing = !!runSiteId && !inputs.some((item) => item.siteId === runSiteId);

  return (
    <Card size="sm" className="hover-lift">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Project Input</span>
          {followsRun ? (
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/15 font-mono text-[10px] text-emerald-700 dark:text-emerald-300"
            >
              följer vald run
            </Badge>
          ) : null}
        </CardTitle>
        <CardDescription className="text-xs">
          Kundprojektet builder utgår ifrån. Är inte en återanvändbar Dossier.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-1">
        <label className="sr-only" htmlFor="project-input-select">
          Project Input
        </label>
        <select
          id="project-input-select"
          className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
          value={selectedSiteId}
          onChange={(event) => onSelect(event.target.value)}
        >
          {inputs.length === 0 ? (
            <option value="">Inga Project Inputs hittade</option>
          ) : null}
          {inputs.map((input) => (
            <option key={input.siteId} value={input.siteId}>
              {input.companyName} ({input.siteId})
            </option>
          ))}
        </select>

        {runSiteIdUnknown ? (
          <p
            data-testid="project-input-run-siteid-unknown"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-2 text-[11px] text-amber-900 dark:text-amber-200"
          >
            Vald run saknar ett känt siteId (unknown). Follow-up kan inte
            följa runen säkert — välj en annan run eller starta en ny via
            prompten.
          </p>
        ) : null}

        {runMissing ? (
          <p
            data-testid="project-input-missing-for-run"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-2 text-[11px] text-amber-900 dark:text-amber-200"
          >
            Vald run använder siteId{" "}
            <span className="font-mono">{runSiteId}</span> men ingen
            Project Input med det id:t finns på disk just nu. Picker:n
            visar därför inte runens DNA — välj manuellt eller starta en
            ny run via prompten.
          </p>
        ) : null}

        {selected ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <dt>scaffold</dt>
            <dd className="truncate font-mono text-foreground/80">{selected.scaffoldId}</dd>
            <dt>variant</dt>
            <dd className="truncate font-mono text-foreground/80">{selected.variantId}</dd>
            <dt>språk</dt>
            <dd className="truncate font-mono text-foreground/80">{selected.language}</dd>
            <dt>källa</dt>
            <dd className="truncate font-mono text-foreground/80">{selected.source}</dd>
          </dl>
        ) : null}
      </CardContent>
    </Card>
  );
}
