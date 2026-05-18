"use client";

import { useCallback } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

import type { ContentBranch } from "../wizard-constants";
import {
  CUISINE_OPTIONS,
  DIETARY_OPTIONS,
  PRICE_TIER_OPTIONS,
} from "../wizard-constants";
import type {
  MenuItem,
  ProductItem,
  ProjectItem,
  ServiceItem,
  TeamMember,
  WizardAnswers,
} from "../wizard-types";
import {
  Chip,
  ChipRow,
  FieldLabel,
  FieldStack,
  HelperText,
  SectionHeader,
  TagListInput,
  TextField,
} from "./step-primitives";

/**
 * Steg 3 — Innehåll. Visar olika fält beroende på vald content-gren
 * (ecommerce, restaurant, salon, ...). Hela steget är frivilligt;
 * operatorn kan hoppa över och fylla i senare via PI-redigeraren.
 */

function genId(): string {
  // Stabil-nog ID för list-keys. Wizardens scope är localhost-only och
  // svaren skickas till backend där servern äger ID-allokering — så
  // crypto.randomUUID() är overkill. Math.random är OK här.
  return `item-${Math.random().toString(36).slice(2, 10)}`;
}

export function ContentStep({
  answers,
  onChange,
  branch,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  branch: ContentBranch;
}) {
  return (
    <FieldStack>
      {branch === "ecommerce" ? (
        <EcommerceContent answers={answers} onChange={onChange} />
      ) : null}
      {branch === "restaurant" ? (
        <RestaurantContent answers={answers} onChange={onChange} />
      ) : null}
      {branch === "salon" ? <SalonContent answers={answers} onChange={onChange} /> : null}
      {branch === "portfolio" ? (
        <PortfolioContent answers={answers} onChange={onChange} />
      ) : null}
      {branch === "consulting" ||
      branch === "business" ||
      branch === "construction" ||
      branch === "legal" ||
      branch === "nonprofit" ||
      branch === "realestate" ||
      branch === "education" ||
      branch === "event" ||
      branch === "hotel" ||
      branch === "minimal" ? (
        <ServicesContent answers={answers} onChange={onChange} branch={branch} />
      ) : null}
    </FieldStack>
  );
}

/* ── E-commerce ─────────────────────────────────────────────────── */

function EcommerceContent({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const addProduct = () => {
    const next: ProductItem = { id: genId(), name: "" };
    onChange({ products: [...answers.products, next] });
  };
  const updateProduct = (id: string, patch: Partial<ProductItem>) => {
    onChange({
      products: answers.products.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    });
  };
  const removeProduct = (id: string) => {
    onChange({ products: answers.products.filter((p) => p.id !== id) });
  };

  return (
    <>
      <div>
        <SectionHeader>Produkter</SectionHeader>
        <HelperText>Lista 3–6 nyckelprodukter. Använd korta namn — full text kommer i sajtens butik.</HelperText>
        <div className="mt-3 flex flex-col gap-3">
          {answers.products.map((product) => (
            <ProductRow
              key={product.id}
              product={product}
              onChange={(patch) => updateProduct(product.id, patch)}
              onRemove={() => removeProduct(product.id)}
            />
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addProduct} className="self-start text-[12px]">
            + Lägg till produkt
          </Button>
        </div>
      </div>

      <div>
        <FieldLabel optional>Prisnivå</FieldLabel>
        <ChipRow>
          {PRICE_TIER_OPTIONS.map((tier) => (
            <Chip
              key={tier}
              label={tier}
              selected={answers.priceTier === tier}
              onToggle={() => onChange({ priceTier: answers.priceTier === tier ? "" : tier })}
            />
          ))}
        </ChipRow>
      </div>

      <div>
        <FieldLabel optional>Unika säljpunkter (USP:er)</FieldLabel>
        <TagListInput
          values={answers.uniqueSellingPoints}
          onChange={(next) => onChange({ uniqueSellingPoints: next })}
          placeholder="t.ex. Fri frakt över 500 kr"
          maxItems={6}
        />
      </div>
    </>
  );
}

function ProductRow({
  product,
  onChange,
  onRemove,
}: {
  product: ProductItem;
  onChange: (patch: Partial<ProductItem>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-card/50 p-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px]">
        <Input
          value={product.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Produktnamn"
          className="h-9 text-[13px]"
        />
        <Input
          value={product.price ?? ""}
          onChange={(e) => onChange({ price: e.target.value })}
          placeholder="Pris (t.ex. 299 kr)"
          className="h-9 text-[13px]"
        />
      </div>
      <Textarea
        value={product.description ?? ""}
        onChange={(e) => onChange({ description: e.target.value })}
        placeholder="Kort beskrivning (valfritt)"
        rows={2}
        className="mt-2 text-[13px]"
      />
      <div className="mt-2 flex justify-end">
        <Button type="button" variant="ghost" size="sm" onClick={onRemove} className="text-[11px] text-muted-foreground">
          Ta bort
        </Button>
      </div>
    </div>
  );
}

/* ── Restaurant ─────────────────────────────────────────────────── */

function RestaurantContent({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const toggle = useCallback(
    (key: "cuisineTags" | "dietaryTags", value: string) => {
      const current = new Set(answers[key]);
      if (current.has(value)) current.delete(value);
      else current.add(value);
      onChange({ [key]: Array.from(current) } as Partial<WizardAnswers>);
    },
    [answers, onChange],
  );

  const addMenuItem = () => {
    const next: MenuItem = { id: genId(), name: "" };
    onChange({ menuItems: [...answers.menuItems, next] });
  };
  const updateMenuItem = (id: string, patch: Partial<MenuItem>) => {
    onChange({
      menuItems: answers.menuItems.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    });
  };
  const removeMenuItem = (id: string) => {
    onChange({ menuItems: answers.menuItems.filter((m) => m.id !== id) });
  };

  return (
    <>
      <div>
        <SectionHeader>Kök & stil</SectionHeader>
        <ChipRow>
          {CUISINE_OPTIONS.map((cuisine) => (
            <Chip
              key={cuisine}
              label={cuisine}
              selected={answers.cuisineTags.includes(cuisine)}
              onToggle={() => toggle("cuisineTags", cuisine)}
            />
          ))}
        </ChipRow>
      </div>

      <div>
        <FieldLabel optional>Kostalternativ</FieldLabel>
        <ChipRow>
          {DIETARY_OPTIONS.map((dietary) => (
            <Chip
              key={dietary}
              label={dietary}
              selected={answers.dietaryTags.includes(dietary)}
              onToggle={() => toggle("dietaryTags", dietary)}
            />
          ))}
        </ChipRow>
      </div>

      <div>
        <FieldLabel optional>Prisnivå</FieldLabel>
        <ChipRow>
          {PRICE_TIER_OPTIONS.map((tier) => (
            <Chip
              key={tier}
              label={tier}
              selected={answers.priceTier === tier}
              onToggle={() => onChange({ priceTier: answers.priceTier === tier ? "" : tier })}
            />
          ))}
        </ChipRow>
      </div>

      <TextField
        label="Bokningslänk"
        type="url"
        optional
        value={answers.bookingUrl}
        onChange={(value) => onChange({ bookingUrl: value })}
        placeholder="https://bord.se/dittforetag"
      />

      <div>
        <SectionHeader>Meny</SectionHeader>
        <HelperText>Några nyckelrätter — full meny kan läggas till senare.</HelperText>
        <div className="mt-3 flex flex-col gap-3">
          {answers.menuItems.map((item) => (
            <div key={item.id} className="rounded-xl border border-border/70 bg-card/50 p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px]">
                <Input
                  value={item.name}
                  onChange={(e) => updateMenuItem(item.id, { name: e.target.value })}
                  placeholder="Rättens namn"
                  className="h-9 text-[13px]"
                />
                <Input
                  value={item.price ?? ""}
                  onChange={(e) => updateMenuItem(item.id, { price: e.target.value })}
                  placeholder="Pris"
                  className="h-9 text-[13px]"
                />
              </div>
              <Textarea
                value={item.description ?? ""}
                onChange={(e) => updateMenuItem(item.id, { description: e.target.value })}
                placeholder="Kort beskrivning"
                rows={2}
                className="mt-2 text-[13px]"
              />
              <div className="mt-2 flex justify-end">
                <Button type="button" variant="ghost" size="sm" onClick={() => removeMenuItem(item.id)} className="text-[11px] text-muted-foreground">
                  Ta bort
                </Button>
              </div>
            </div>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addMenuItem} className="self-start text-[12px]">
            + Lägg till menyrad
          </Button>
        </div>
      </div>
    </>
  );
}

/* ── Salon / Healthcare / Fitness ───────────────────────────────── */

function SalonContent({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const addService = () => {
    const next: ServiceItem = { id: genId(), name: "" };
    onChange({ services: [...answers.services, next] });
  };
  const updateService = (id: string, patch: Partial<ServiceItem>) => {
    onChange({ services: answers.services.map((s) => (s.id === id ? { ...s, ...patch } : s)) });
  };
  const removeService = (id: string) => {
    onChange({ services: answers.services.filter((s) => s.id !== id) });
  };

  const addTeam = () => {
    const next: TeamMember = { id: genId(), name: "" };
    onChange({ team: [...answers.team, next] });
  };
  const updateTeam = (id: string, patch: Partial<TeamMember>) => {
    onChange({ team: answers.team.map((t) => (t.id === id ? { ...t, ...patch } : t)) });
  };
  const removeTeam = (id: string) => {
    onChange({ team: answers.team.filter((t) => t.id !== id) });
  };

  return (
    <>
      <div>
        <SectionHeader>Behandlingar och tjänster</SectionHeader>
        <div className="flex flex-col gap-3">
          {answers.services.map((service) => (
            <div key={service.id} className="rounded-xl border border-border/70 bg-card/50 p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px_100px]">
                <Input value={service.name} onChange={(e) => updateService(service.id, { name: e.target.value })} placeholder="Behandling" className="h-9 text-[13px]" />
                <Input value={service.price ?? ""} onChange={(e) => updateService(service.id, { price: e.target.value })} placeholder="Pris" className="h-9 text-[13px]" />
                <Input value={service.durationMinutes?.toString() ?? ""} onChange={(e) => updateService(service.id, { durationMinutes: Number(e.target.value) || undefined })} placeholder="Min" type="number" className="h-9 text-[13px]" />
              </div>
              <div className="mt-2 flex justify-end">
                <Button type="button" variant="ghost" size="sm" onClick={() => removeService(service.id)} className="text-[11px] text-muted-foreground">Ta bort</Button>
              </div>
            </div>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addService} className="self-start text-[12px]">+ Lägg till behandling</Button>
        </div>
      </div>

      <div>
        <SectionHeader>Team</SectionHeader>
        <div className="flex flex-col gap-3">
          {answers.team.map((member) => (
            <div key={member.id} className="rounded-xl border border-border/70 bg-card/50 p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Input value={member.name} onChange={(e) => updateTeam(member.id, { name: e.target.value })} placeholder="Namn" className="h-9 text-[13px]" />
                <Input value={member.role ?? ""} onChange={(e) => updateTeam(member.id, { role: e.target.value })} placeholder="Roll" className="h-9 text-[13px]" />
              </div>
              <div className="mt-2 flex justify-end">
                <Button type="button" variant="ghost" size="sm" onClick={() => removeTeam(member.id)} className="text-[11px] text-muted-foreground">Ta bort</Button>
              </div>
            </div>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addTeam} className="self-start text-[12px]">+ Lägg till medarbetare</Button>
        </div>
      </div>

      <TextField label="Bokningslänk" type="url" optional value={answers.bookingUrl} onChange={(value) => onChange({ bookingUrl: value })} placeholder="https://bokadirekt.se/…" />
    </>
  );
}

/* ── Portfolio / Photo / Music ──────────────────────────────────── */

function PortfolioContent({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const addProject = () => {
    const next: ProjectItem = { id: genId(), name: "" };
    onChange({ projects: [...answers.projects, next] });
  };
  const updateProject = (id: string, patch: Partial<ProjectItem>) => {
    onChange({ projects: answers.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)) });
  };
  const removeProject = (id: string) => {
    onChange({ projects: answers.projects.filter((p) => p.id !== id) });
  };

  return (
    <>
      <SectionHeader>Projekt och case</SectionHeader>
      <HelperText>3–6 starka projekt. Beskriv vad du löste och för vem.</HelperText>
      <div className="mt-3 flex flex-col gap-3">
        {answers.projects.map((project) => (
          <div key={project.id} className="rounded-xl border border-border/70 bg-card/50 p-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Input value={project.name} onChange={(e) => updateProject(project.id, { name: e.target.value })} placeholder="Projektnamn" className="h-9 text-[13px]" />
              <Input value={project.client ?? ""} onChange={(e) => updateProject(project.id, { client: e.target.value })} placeholder="Kund (valfritt)" className="h-9 text-[13px]" />
            </div>
            <Textarea value={project.description ?? ""} onChange={(e) => updateProject(project.id, { description: e.target.value })} placeholder="Vad gjorde du? Vilket resultat?" rows={2} className="mt-2 text-[13px]" />
            <div className="mt-2 flex justify-end">
              <Button type="button" variant="ghost" size="sm" onClick={() => removeProject(project.id)} className="text-[11px] text-muted-foreground">Ta bort</Button>
            </div>
          </div>
        ))}
        <Button type="button" variant="ghost" size="sm" onClick={addProject} className="self-start text-[12px]">+ Lägg till projekt</Button>
      </div>
    </>
  );
}

/* ── Generic services (business / consulting / legal / ...) ─────── */

function ServicesContent({
  answers,
  onChange,
  branch,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  branch: ContentBranch;
}) {
  const addService = () => {
    const next: ServiceItem = { id: genId(), name: "" };
    onChange({ services: [...answers.services, next] });
  };
  const updateService = (id: string, patch: Partial<ServiceItem>) => {
    onChange({ services: answers.services.map((s) => (s.id === id ? { ...s, ...patch } : s)) });
  };
  const removeService = (id: string) => {
    onChange({ services: answers.services.filter((s) => s.id !== id) });
  };

  const labelMap: Partial<Record<ContentBranch, { section: string; placeholder: string; uspLabel: string }>> = {
    consulting: { section: "Tjänsteområden", placeholder: "t.ex. Digital strategi", uspLabel: "Unika styrkor" },
    business: { section: "Tjänster vi erbjuder", placeholder: "t.ex. Husmålning", uspLabel: "Varför välja oss" },
    construction: { section: "Tjänsteområden", placeholder: "t.ex. Köksrenovering", uspLabel: "Vad ni levererar" },
    legal: { section: "Verksamhetsområden", placeholder: "t.ex. Affärsjuridik", uspLabel: "Erfarenhet" },
    nonprofit: { section: "Vi gör", placeholder: "t.ex. Stödjer hemlösa familjer", uspLabel: "Mission och värden" },
    realestate: { section: "Tjänster", placeholder: "t.ex. Värdering av bostadsrätt", uspLabel: "Erfarenhet och resultat" },
    education: { section: "Kurser och program", placeholder: "t.ex. Onlinekurs i UX", uspLabel: "Vad gör er unika" },
    event: { section: "Eventtyper", placeholder: "t.ex. Företagsfest", uspLabel: "Det vi gör bäst" },
    hotel: { section: "Faciliteter", placeholder: "t.ex. Spa och frukost ingår", uspLabel: "Vad gästerna älskar" },
    minimal: { section: "Ämnesområden", placeholder: "t.ex. Innovation, design, ledarskap", uspLabel: "Huvudbudskap" },
  };
  const labels = labelMap[branch] ?? { section: "Tjänster", placeholder: "Tjänst", uspLabel: "Vad ni levererar" };

  return (
    <>
      <div>
        <SectionHeader>{labels.section}</SectionHeader>
        <div className="flex flex-col gap-3">
          {answers.services.map((service) => (
            <div key={service.id} className="rounded-xl border border-border/70 bg-card/50 p-3">
              <Input value={service.name} onChange={(e) => updateService(service.id, { name: e.target.value })} placeholder={labels.placeholder} className="h-9 text-[13px]" />
              <Textarea value={service.description ?? ""} onChange={(e) => updateService(service.id, { description: e.target.value })} placeholder="Kort beskrivning (valfritt)" rows={2} className="mt-2 text-[13px]" />
              <div className="mt-2 flex justify-end">
                <Button type="button" variant="ghost" size="sm" onClick={() => removeService(service.id)} className="text-[11px] text-muted-foreground">Ta bort</Button>
              </div>
            </div>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addService} className="self-start text-[12px]">+ Lägg till</Button>
        </div>
      </div>

      <div>
        <FieldLabel optional>{labels.uspLabel}</FieldLabel>
        <TagListInput
          values={answers.uniqueSellingPoints}
          onChange={(next) => onChange({ uniqueSellingPoints: next })}
          placeholder="Skriv och tryck Enter…"
          maxItems={6}
        />
      </div>
    </>
  );
}
