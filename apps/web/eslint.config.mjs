import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import reactHooks from "eslint-plugin-react-hooks";

const nextRules = [...nextCoreWebVitals, ...nextTypescript].map((config) => ({
  ...config,
  plugins: {
    ...(config.plugins ?? {}),
    "react-hooks": reactHooks,
  },
  rules: {
    ...(config.rules ?? {}),
    // Match Sajtmaskins original eslint-config: nya React 19-strikt regler är
    // warnings, inte errors. apps/web ärver dessa val tills vi har bandwidth
    // för att städa hooks-code.
    "react-hooks/immutability": "warn",
    "react-hooks/preserve-manual-memoization": "warn",
    "react-hooks/purity": "warn",
    "react-hooks/refs": "warn",
    "react-hooks/set-state-in-effect": "warn",
    "react-hooks/static-components": "warn",
  },
}));

export default defineConfig([
  ...nextRules,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
      "no-console": ["warn", { allow: ["warn", "error", "info"] }],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
]);
