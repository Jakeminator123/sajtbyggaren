"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type DossierOption = {
  siteId: string;
  companyName: string;
  scaffoldId: string;
  variantId: string;
  language: string;
};

type DossierPickerProps = {
  dossiers: DossierOption[];
  selectedDossierId: string;
  onSelect: (siteId: string) => void;
};

export function DossierPicker({
  dossiers,
  selectedDossierId,
  onSelect,
}: DossierPickerProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Dossier</CardTitle>
      </CardHeader>
      <CardContent>
        <select
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={selectedDossierId}
          onChange={(event) => onSelect(event.target.value)}
        >
          {dossiers.map((dossier) => (
            <option key={dossier.siteId} value={dossier.siteId}>
              {dossier.companyName} ({dossier.siteId})
            </option>
          ))}
        </select>
      </CardContent>
    </Card>
  );
}
