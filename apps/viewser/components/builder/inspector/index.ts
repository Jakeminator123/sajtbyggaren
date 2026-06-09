// ComparePreviewModal re-exporteras MEDVETET INTE här. Den drar in
// StackBlitz-modulgrafen (``compare-preview-modal`` använder
// ``await import("@stackblitz/sdk")``), och eftersom builder-shell statiskt
// importerar denna barrel skulle en re-export lägga compare-preview-modal i
// studio-sidans eager-graf → SDK-chunken skulle eager-scriptas vid varje
// studio-load (bundle-bloat). Konsumenten (versions-tab) laddar den i stället
// lazy via en runtime ``import()`` direkt från fil-pathen (ADR 0033).
export { SiteInspectorSheet } from "@/components/builder/inspector/site-inspector-sheet";
export { VariantsTab } from "@/components/builder/inspector/variants-tab";
export { VersionsTab } from "@/components/builder/inspector/versions-tab";
