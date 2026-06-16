import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  summarizeChangeSet,
  type RunChangeSet,
  type ChangeSetGenerativeComponent,
} from "./build-changes";

/**
 * Bekräftar att generativa tillägg (ADR 0061/0064) blir en EXAKT
 * "Ändrat"-rad i FloatingChat i stället för en generisk "Klart!". Testet
 * importerar `node:test` explicit (i st.f. den globalt injicerade
 * `describe`/`it`-stilen) så det går att köra lokalt med `npx tsx --test`.
 */

function changeSet(overrides: Partial<RunChangeSet> = {}): RunChangeSet {
  return {
    previousRunId: "run-prev",
    routesAdded: [],
    routesRemoved: [],
    variantBefore: null,
    variantAfter: null,
    appliedFocusSections: [],
    generativeComponentsAdded: [],
    ...overrides,
  };
}

function gen(
  overrides: Partial<ChangeSetGenerativeComponent> = {},
): ChangeSetGenerativeComponent {
  return {
    recipe: "image-placeholder-grid",
    count: 6,
    routeId: "home",
    id: "image-placeholder-grid",
    ...overrides,
  };
}

describe("summarizeChangeSet — generativa komponenter", () => {
  it("namnger en bildgrid med antal platshållare", () => {
    const changes = summarizeChangeSet(
      changeSet({ generativeComponentsAdded: [gen({ count: 6 })] }),
    );
    assert.deepEqual(changes, [
      { category: "media", label: "Bildgrid med 6 platshållare tillagd" },
    ]);
  });

  it("namnger ett kontakt-CTA-block", () => {
    const changes = summarizeChangeSet(
      changeSet({
        generativeComponentsAdded: [
          gen({
            recipe: "cta-contact-block",
            count: 1,
            id: "cta-contact-block",
          }),
        ],
      }),
    );
    assert.deepEqual(changes, [
      { category: "content", label: "Kontakt-CTA tillagd" },
    ]);
  });

  it("lägger till positionssuffix endast för top/bottom", () => {
    const top = summarizeChangeSet(
      changeSet({ generativeComponentsAdded: [gen({ position: "top" })] }),
    );
    assert.equal(top[0].label, "Bildgrid med 6 platshållare tillagd (överst)");

    const bottom = summarizeChangeSet(
      changeSet({
        generativeComponentsAdded: [gen({ position: "bottom", id: "g2" })],
      }),
    );
    assert.equal(
      bottom[0].label,
      "Bildgrid med 6 platshållare tillagd (nederst)",
    );

    // before-contact (default-slotten) ger ingen brusig parentes.
    const beforeContact = summarizeChangeSet(
      changeSet({
        generativeComponentsAdded: [
          gen({ position: "before-contact", id: "g3" }),
        ],
      }),
    );
    assert.equal(beforeContact[0].label, "Bildgrid med 6 platshållare tillagd");
  });

  it("kombinerar route-deltan och generativa tillägg men cappar på 3 rader", () => {
    const changes = summarizeChangeSet(
      changeSet({
        routesAdded: ["/tjanster", "/om-oss"],
        generativeComponentsAdded: [
          gen({ id: "g1" }),
          gen({ id: "g2", recipe: "cta-contact-block", count: 1 }),
        ],
      }),
    );
    // 2 routes + 1 generativ = 3 (cappad), generativ #2 ryms inte.
    assert.equal(changes.length, 3);
    assert.deepEqual(changes[0], {
      category: "structure",
      label: "Sidan /tjanster tillagd",
    });
    assert.equal(changes[2].label, "Bildgrid med 6 platshållare tillagd");
  });

  it("ger inga generativa rader när listan är tom eller saknas", () => {
    assert.deepEqual(summarizeChangeSet(changeSet()), []);
    // Bakåtkompatibilitet: en wire-changeSet från en äldre server saknar
    // fältet helt — `?? []`-skyddet får inte krascha.
    const legacy = {
      previousRunId: "run-prev",
      routesAdded: [],
      routesRemoved: [],
      variantBefore: null,
      variantAfter: null,
      appliedFocusSections: [],
    } as unknown as RunChangeSet;
    assert.deepEqual(summarizeChangeSet(legacy), []);
  });
});
