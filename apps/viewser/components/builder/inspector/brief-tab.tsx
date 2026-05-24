"use client";

import {
  Briefcase,
  Building2,
  MapPin,
  MessageSquare,
  Target,
} from "lucide-react";

import { QuickPromptButton } from "@/components/builder/inspector/quick-prompt-button";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";

/**
 * Brief & Plan-tab: read-only sammanfattning av vad briefModel +
 * planningModel kom fram till. Operatören kan se företagsnamn, ton,
 * målgrupp, tjänster, conversion-goals, scaffold/variant/starter och
 * planner-noter — och skicka snabbprompts för att ändra varje fält.
 *
 * Snabbprompterna är skrivna i imperativ form mot briefModel:s
 * vokabulär ("Ändra tonen till...") så briefen kan re-tolkas
 * korrekt vid nästa följdprompt-bygge.
 */

type BriefTabProps = {
  bundle: RunArtefactBundle;
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void;
};

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Briefcase;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
        <Icon className="h-3 w-3" aria-hidden />
        {title}
      </div>
      {children}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-muted/60 border-border/40 text-foreground/80 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] tracking-tight">
      {children}
    </span>
  );
}

export function BriefTab({
  bundle,
  isBuilding,
  pendingPrompt,
  onPrompt,
}: BriefTabProps) {
  const brief = bundle.siteBrief ?? {};
  const plan = bundle.sitePlan ?? {};

  const companyName = asString(brief.companyName);
  const businessType = asString(brief.businessTypeGuess);
  const tone = asStringArray(brief.tone);
  const audience = asStringArray(brief.targetAudience);
  const capabilities = asStringArray(brief.requestedCapabilities);
  const services = asStringArray(brief.servicesMentioned);
  const goals = asStringArray(brief.conversionGoals);
  const location = asString(brief.locationHint);
  const notes = asString(brief.notesForPlanner);

  const scaffoldId = asString(plan.scaffoldId);
  const variantId = asString(plan.variantId);
  const starterId = asString(plan.starterId);

  return (
    <div className="flex flex-col gap-5">
      <Section icon={Building2} title="Företag">
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-foreground text-[14px] font-medium tracking-tight">
              {companyName ?? "—"}
            </span>
            {businessType ? <Chip>{businessType}</Chip> : null}
          </div>
          {location ? (
            <p className="text-muted-foreground inline-flex items-center gap-1 text-[11.5px]">
              <MapPin className="h-3 w-3" aria-hidden />
              {location}
            </p>
          ) : null}
        </div>
      </Section>

      <Section icon={MessageSquare} title="Ton & målgrupp">
        <div className="flex flex-col gap-2">
          {tone.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {tone.map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-[11.5px] italic">
              Ingen ton angiven.
            </p>
          )}
          {audience.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {audience.map((a) => (
                <Chip key={a}>{a}</Chip>
              ))}
            </div>
          ) : null}
          <div className="mt-1 flex flex-wrap gap-1.5">
            <QuickPromptButton
              label="Gör mer playful"
              prompt="Ändra sajtens ton till mer playful, lekfull och energifylld. Använd starkare uttryck och korta meningar."
              isBuilding={isBuilding}
              isPending={
                pendingPrompt ===
                "Ändra sajtens ton till mer playful, lekfull och energifylld. Använd starkare uttryck och korta meningar."
              }
              onSelect={onPrompt}
            />
            <QuickPromptButton
              label="Gör mer formell"
              prompt="Ändra sajtens ton till mer formell, professionell och informativ. Längre meningar, mindre superlativer."
              isBuilding={isBuilding}
              isPending={
                pendingPrompt ===
                "Ändra sajtens ton till mer formell, professionell och informativ. Längre meningar, mindre superlativer."
              }
              onSelect={onPrompt}
            />
            <QuickPromptButton
              label="Mer minimalistiskt"
              prompt="Skär ner mängden text på sajten. Behåll bara det viktigaste. Gör allt mer minimalistiskt och Apple-likt."
              isBuilding={isBuilding}
              isPending={
                pendingPrompt ===
                "Skär ner mängden text på sajten. Behåll bara det viktigaste. Gör allt mer minimalistiskt och Apple-likt."
              }
              onSelect={onPrompt}
            />
          </div>
        </div>
      </Section>

      {services.length > 0 ? (
        <Section icon={Briefcase} title="Tjänster">
          <div className="flex flex-wrap gap-1.5">
            {services.map((s) => (
              <Chip key={s}>{s}</Chip>
            ))}
          </div>
          <div className="mt-2">
            <QuickPromptButton
              label="Skriv om alla tjänstebeskrivningar"
              prompt="Skriv om alla tjänstebeskrivningar på sajten. Gör dem konkreta, värdebaserade och korta — max 2 meningar per tjänst."
              isBuilding={isBuilding}
              isPending={
                pendingPrompt ===
                "Skriv om alla tjänstebeskrivningar på sajten. Gör dem konkreta, värdebaserade och korta — max 2 meningar per tjänst."
              }
              onSelect={onPrompt}
            />
          </div>
        </Section>
      ) : null}

      {capabilities.length > 0 ? (
        <Section icon={Target} title="Önskade funktioner">
          <div className="flex flex-wrap gap-1.5">
            {capabilities.map((c) => (
              <Chip key={c}>{c}</Chip>
            ))}
          </div>
        </Section>
      ) : null}

      {goals.length > 0 ? (
        <Section icon={Target} title="Konverteringsmål">
          <div className="flex flex-wrap gap-1.5">
            {goals.map((g) => (
              <Chip key={g}>{g}</Chip>
            ))}
          </div>
          <div className="mt-2">
            <QuickPromptButton
              label="Förstärk CTA:erna"
              prompt="Förstärk alla call-to-actions på sajten. Gör dem mer aktiva, specifika och tydligt kopplade till konverteringsmålen."
              isBuilding={isBuilding}
              isPending={
                pendingPrompt ===
                "Förstärk alla call-to-actions på sajten. Gör dem mer aktiva, specifika och tydligt kopplade till konverteringsmålen."
              }
              onSelect={onPrompt}
            />
          </div>
        </Section>
      ) : null}

      {scaffoldId || variantId || starterId ? (
        <Section icon={Briefcase} title="Teknisk grund">
          <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-[11.5px]">
            {scaffoldId ? (
              <>
                <dt className="text-muted-foreground">Scaffold</dt>
                <dd className="text-foreground font-mono text-[11px]">
                  {scaffoldId}
                </dd>
              </>
            ) : null}
            {variantId ? (
              <>
                <dt className="text-muted-foreground">Variant</dt>
                <dd className="text-foreground font-mono text-[11px]">
                  {variantId}
                </dd>
              </>
            ) : null}
            {starterId ? (
              <>
                <dt className="text-muted-foreground">Starter</dt>
                <dd className="text-foreground font-mono text-[11px]">
                  {starterId}
                </dd>
              </>
            ) : null}
          </dl>
        </Section>
      ) : null}

      {notes ? (
        <Section icon={MessageSquare} title="Planner-noter">
          <p className="text-muted-foreground bg-muted/30 border-border/40 rounded-md border p-2 text-[11.5px] leading-relaxed italic">
            &ldquo;{notes}&rdquo;
          </p>
        </Section>
      ) : null}
    </div>
  );
}
