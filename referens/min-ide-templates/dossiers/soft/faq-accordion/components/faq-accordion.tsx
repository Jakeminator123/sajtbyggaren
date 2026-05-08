"use client";

import { useEffect, useRef, type ReactNode } from "react";

export interface FaqItem {
  question: string;
  answer: ReactNode;
}

interface FaqAccordionProps {
  items: FaqItem[];
  title?: string;
  description?: string;
  singleOpen?: boolean;
  className?: string;
}

export function FaqAccordion({
  items,
  title,
  description,
  singleOpen = false,
  className,
}: FaqAccordionProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!singleOpen) return;
    const root = containerRef.current;
    if (!root) return;
    const detailsList = Array.from(root.querySelectorAll<HTMLDetailsElement>("details"));

    function handleToggle(event: Event) {
      const target = event.target as HTMLDetailsElement;
      if (!target.open) return;
      for (const other of detailsList) {
        if (other !== target && other.open) {
          other.open = false;
        }
      }
    }

    for (const el of detailsList) el.addEventListener("toggle", handleToggle);
    return () => {
      for (const el of detailsList) el.removeEventListener("toggle", handleToggle);
    };
  }, [singleOpen, items]);

  return (
    <section className={className}>
      {(title || description) && (
        <header className="mb-8 max-w-2xl">
          {title && <h2 className="text-2xl font-semibold text-foreground sm:text-3xl">{title}</h2>}
          {description && (
            <p className="mt-2 text-base text-muted-foreground">{description}</p>
          )}
        </header>
      )}
      <div ref={containerRef} className="divide-y divide-border rounded-lg border border-border">
        {items.map((item, idx) => (
          <details
            key={`${idx}-${item.question}`}
            className="group [&_summary::-webkit-details-marker]:hidden"
          >
            <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4 text-left text-sm font-medium text-foreground transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-base">
              <span>{item.question}</span>
              <span
                aria-hidden="true"
                className="ml-2 inline-flex h-5 w-5 shrink-0 items-center justify-center text-lg font-light leading-none opacity-60"
              >
                <span className="block group-open:hidden">+</span>
                <span className="hidden group-open:block">−</span>
              </span>
            </summary>
            <div className="px-5 pb-5 pt-1 text-sm leading-relaxed text-muted-foreground sm:text-base">
              {typeof item.answer === "string" ? <p>{item.answer}</p> : item.answer}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
