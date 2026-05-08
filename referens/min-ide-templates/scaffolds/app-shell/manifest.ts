import type { ScaffoldManifest } from "../types";
import { loadScaffoldFiles } from "../load-scaffold-files";

export const appShellManifest: ScaffoldManifest = {
  id: "app-shell",
  label: "App Shell",
  description:
    "Operational app shell with sidebar navigation, workspace summaries, queue tables, and execution-focused content areas.",
  siteKind: "app",
  complexity: "medium",
  structureProfile: "application-shell",
  contentProfile: "workspace-tools",
  features: ["auth", "sidebar-layout", "settings", "dash-widgets"],
  allowedBuildIntents: ["app"],
  tags: ["app-shell", "workspace", "operations", "crm", "saas", "backoffice", "admin", "portal", "internal-tool", "sidebar", "kontrollpanel", "verktyg"],
  promptHints: [
    "Use this scaffold for operational apps, internal tools, and workflow-oriented SaaS backoffices.",
    "Keep the sidebar + main workspace pattern, but prioritize queues, tasks, and action states over analytics storytelling.",
    "Use actionable tables, statuses, and task cards that map to real product workflows.",
    "Preserve the shell structure while adapting entities, labels, and actions to the user's domain.",
  ],
  qualityChecklist: [
    "Navigation shell, app density, and workspace feel should stay more prominent than marketing content.",
    "Primary panels, tables, and summaries should map to the user's real product/workflow.",
    "Account, billing, settings, or workspace affordances should feel layerable without breaking the shell.",
  ],
  research: {
    upgradeTargets: [
      "Add role-based navigation sections and per-role entry dashboards.",
      "Include bulk actions and row-level quick actions in queue tables.",
      "Add command palette and keyboard shortcuts for power-user workflows.",
    ],
    referenceTemplates: [
      { id: "multi-tenant-apps-turso-per-user-starter", title: "Turso Per-User Starter", categorySlug: "multi-tenant-apps", qualityScore: 96, strengths: ["verified Next.js codebase", "multi-tenant patterns", "user workspace isolation"] },
      { id: "multi-tenant-apps-b2b-multi-tenant-starter-kit", title: "B2B Multi-Tenant Starter Kit", categorySlug: "multi-tenant-apps", qualityScore: 94, strengths: ["verified Next.js codebase", "B2B app patterns", "team workspace shell"] },
      { id: "admin-dashboard-modernize-next-js-admin-dashboard-template", title: "Modernize Next.js Admin Dashboard", categorySlug: "admin-dashboard", qualityScore: 96, strengths: ["verified Next.js codebase", "sidebar navigation", "settings and admin patterns"] },
    ],
  },
  files: loadScaffoldFiles("app-shell"),
};
