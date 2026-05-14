"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Project Input</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Välj Project Input (kundprojekt/Deep Brief) som builder ska använda.
          Detta är inte en capability Dossier - en Dossier är en återanvändbar
          legokloss som kan kopplas på vilken sajt som helst.
        </p>
        <select
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={selectedSiteId}
          onChange={(event) => onSelect(event.target.value)}
        >
          {inputs.map((input) => (
            <option key={input.siteId} value={input.siteId}>
              {input.companyName} ({input.siteId}, {input.source})
            </option>
          ))}
        </select>
      </CardContent>
    </Card>
  );
}
