// Grundarkort för /om-oss. Foton saknas ännu → interim monogram-avatar
// (initialer) som senare byts mot b-v-porträtt utan att layouten ändras.
// Roll-texten är operatörens verbatim-beskrivning.
export function FounderCard({
  name,
  role,
  initials,
}: {
  name: string;
  role: string;
  initials: string;
}) {
  return (
    <div className="border-border/60 hover-lift flex items-center gap-4 rounded-2xl border p-5 sm:p-6">
      <div
        aria-hidden
        className="bg-foreground text-background grid size-14 shrink-0 place-items-center rounded-2xl text-[16px] font-semibold tracking-tight sm:size-16 sm:text-[18px]"
      >
        {initials}
      </div>
      <div className="min-w-0">
        <p className="text-foreground text-[16px] font-semibold tracking-tight">
          {name}
        </p>
        <p className="text-muted-foreground mt-0.5 text-[14px] leading-relaxed">
          {role}
        </p>
      </div>
    </div>
  );
}
