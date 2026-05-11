"use client"

import { useEffect, useRef, useState } from "react"

const GREETING =
  "Hej! Vilken typ av hemsida vill du bygga? Berätta om ditt företag eller din idé så skapar vi något fantastiskt tillsammans."

const GREETING_DELAY_MS = 1000
const TYPEWRITER_SPEED_MS = 25

export const LANDING_SUGGESTIONS = [
  "Företagssajt med kontaktformulär",
  "Portfolio för fotograf eller designer",
  "Restaurang med meny och bordsbokning",
  "Webshop för hudvård och skönhet",
  "Landningssida för ny app",
  "Konsultbolag inom IT",
  "Frisörsalong med onlinebokning",
  "Byggföretag med projektgalleri",
  "Advokatbyrå med teamöversikt",
  "Café med meny och öppettider",
  "E-handel för kläder och mode",
  "Tandläkare med tidbokning",
  "Startup med produktpresentation",
  "Hantverkare med referensjobb",
  "Eventbyrå med tidigare evenemang",
  "Personlig tränare med bokningssystem",
  "Redovisningsbyrå med tjänsteöversikt",
  "Blogg om resor och livsstil",
  "Fastighetsbolag med objektvisning",
  "Webshop för inredning och möbler",
  "Ideell förening med medlemssidor",
  "Musikartist med spelschema",
  "Hotell med rumsbeskrivningar",
  "Industriföretag med produktkatalog",
  "Mäklare med bostadslistningar",
]

export interface LandingChatState {
  /** The greeting text being typed (partial during animation) */
  greetingDisplayed: string
  /** True once the greeting typewriter is finished */
  greetingDone: boolean
}

export function useLandingChat(): LandingChatState {
  const [greetingDisplayed, setGreetingDisplayed] = useState("")
  const [greetingDone, setGreetingDone] = useState(false)
  const greetingStarted = useRef(false)

  useEffect(() => {
    if (greetingStarted.current) return
    greetingStarted.current = true

    let charIndex = 0
    const delayTimer = setTimeout(() => {
      const interval = setInterval(() => {
        charIndex++
        setGreetingDisplayed(GREETING.slice(0, charIndex))
        if (charIndex >= GREETING.length) {
          clearInterval(interval)
          setGreetingDone(true)
        }
      }, TYPEWRITER_SPEED_MS)
      return () => clearInterval(interval)
    }, GREETING_DELAY_MS)

    return () => clearTimeout(delayTimer)
  }, [])

  return {
    greetingDisplayed,
    greetingDone,
  }
}
