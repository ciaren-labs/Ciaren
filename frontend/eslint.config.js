import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Flags synchronous setState in an effect (e.g. "reset form state when a
      // dialog opens"). That's a deliberate, widely-used pattern in this
      // codebase's controlled dialogs, not a bug — kept as a warning rather
      // than disabled so genuinely new cascading-render effects still surface.
      'react-hooks/set-state-in-effect': 'warn',
      // Flags "const Icon = lookupFn(type); <Icon />" as creating a component
      // during render. Every occurrence in this codebase resolves through a
      // module-level Record<string, LucideIcon> lookup table (see
      // lib/nodeVisuals.ts), so the reference is stable across renders — the
      // rule can't prove that and false-positives on the whole icon-lookup
      // convention used throughout the node/run visuals.
      'react-hooks/static-components': 'warn',
    },
  },
  {
    files: ['**/__tests__/**/*.{ts,tsx}', '**/*.test.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  {
    // Renders a different config shape per node type (~30 node types) off one
    // dynamic `config: Record<string, any>` object. Typing it properly means
    // a per-node-type config schema, not a local fix — swapping `any` for
    // `unknown` here alone cascades into ~80 unrelated type errors at every
    // field read. Tracked as follow-up work rather than done ad hoc.
    files: ['src/components/flow/NodeConfigForm.tsx'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
)
