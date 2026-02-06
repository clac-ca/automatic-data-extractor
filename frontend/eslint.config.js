import path from "node:path";
import { fileURLToPath } from "node:url";

import js from "@eslint/js";
import globals from "globals";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist", "build"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      react.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      parserOptions: {
        project: ["./tsconfig.json"],
        tsconfigRootDir: path.dirname(fileURLToPath(import.meta.url)),
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.vitest,
      },
    },
    plugins: {
      "jsx-a11y": jsxA11y,
      "react-hooks": reactHooks,
    },
    settings: {
      react: {
        version: "detect",
      },
    },
    rules: {
      ...jsxA11y.configs.recommended.rules,
      "jsx-a11y/click-events-have-key-events": "off",
      "jsx-a11y/no-autofocus": "off",
      "jsx-a11y/no-noninteractive-element-interactions": "off",
      "jsx-a11y/role-supports-aria-props": "off",
      "react-refresh/only-export-components": "off",
      "react/react-in-jsx-scope": "off",
      "react/jsx-uses-react": "off",
      "react/no-unknown-property": "off",
      "react/prop-types": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-hooks/rules-of-hooks": "error",
      "react/no-unescaped-entities": "off",
      "no-control-regex": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/types/generated/openapi",
              message: "Import app-facing types from @/types, not the raw generated file.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/types/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": "off",
    },
  },
]);
