import * as React from "react"
import { cn } from "@/lib/utils"

type FaqItem = {
  question: string
  answer: React.ReactNode
  defaultOpen?: boolean
}

export interface FaqAccordionProps
  extends React.HTMLAttributes<HTMLDivElement> {
  items: FaqItem[]
  type?: "single" | "multiple"
}

export function FaqAccordion({
  items,
  type = "single",
  className,
  ...props
}: FaqAccordionProps) {
  const fallbackOpen = React.useMemo(() => {
    if (type === "multiple") {
      return items
        .map((item, index) => (item.defaultOpen ? String(index) : null))
        .filter(Boolean) as string[]
    }

    const firstOpenIndex = items.findIndex((item) => item.defaultOpen)
    return firstOpenIndex >= 0 ? String(firstOpenIndex) : undefined
  }, [items, type])

  if (type === "multiple") {
    return (
      <div className={cn("w-full", className)} {...props}>
        {items.map((item, index) => (
          <details
            key={index}
            open={(fallbackOpen as string[])?.includes(String(index))}
            className="group border-b"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-left font-medium outline-none transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 [&::-webkit-details-marker]:hidden">
              <span>{item.question}</span>
              <span
                aria-hidden="true"
                className="text-muted-foreground transition-transform duration-200 group-open:rotate-180"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </span>
            </summary>
            <div className="pb-4 pt-0 text-sm text-muted-foreground">
              {item.answer}
            </div>
          </details>
        ))}
      </div>
    )
  }

  return (
    <div className={cn("w-full", className)} {...props}>
      {items.map((item, index) => (
        <FaqSingleItem
          key={index}
          question={item.question}
          defaultOpen={fallbackOpen === String(index)}
        >
          {item.answer}
        </FaqSingleItem>
      ))}
    </div>
  )
}

interface FaqSingleItemProps {
  question: string
  children: React.ReactNode
  defaultOpen?: boolean
}

function FaqSingleItem({
  question,
  children,
  defaultOpen = false,
}: FaqSingleItemProps) {
  const id = React.useId()
  const [open, setOpen] = React.useState(defaultOpen)

  return (
    <div className="border-b">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`faq-panel-${id}`}
          onClick={() => setOpen((prev) => !prev)}
          className="flex w-full items-center justify-between gap-4 py-4 text-left font-medium transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <span>{question}</span>
          <span
            aria-hidden="true"
            className={cn(
              "text-muted-foreground transition-transform duration-200",
              open && "rotate-180"
            )}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </button>
      </h3>
      <div
        id={`faq-panel-${id}`}
        hidden={!open}
        className="pb-4 pt-0 text-sm text-muted-foreground"
      >
        {children}
      </div>
    </div>
  )
}
