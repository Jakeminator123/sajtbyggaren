"use client";

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
};

export function ProjectInputPicker({
  inputs,
  selectedSiteId,
  onSelect,
}: ProjectInputPickerProps) {
  const selected = inputs.find((input) => input.siteId === selectedSiteId);

  return (
    <Card size="sm" className="hover-lift">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Project Input</CardTitle>
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
