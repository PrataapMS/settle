# 10 · Security and privacy

## Data

- All decision data stays in the user's browser (IndexedDB). There is no Settle server for data.
- Network destinations: OpenRouter (reasoning and fallback router), TypeSafe (Jev, if enabled), and the app host for static files. Enforce this with a Content Security Policy: `connect-src 'self' https://openrouter.ai https://<jev-host>`.
- What leaves the device per turn: the user's message, the current frame and state, and the last two replies, sent to the model provider through OpenRouter. Say this plainly in Settings → Privacy, and link to OpenRouter's privacy and data-retention settings, where users can restrict providers that train on data.
- No analytics or error reporting by default. If added later, make them opt-in and never send message text.

## Keys

- The OpenRouter key comes from OAuth PKCE or is pasted by the user, and is stored in IndexedDB (`ui.openrouter_key`).
- It is never logged, exported, put in a URL or placed in `VITE_*` variables.
- Development keys live only in `.env.local`, which must be in `.gitignore`, and are injected by the Vite dev proxy.
- "Disconnect" deletes the key. Recommend users set a credit limit on their OpenRouter key.

## Prompt injection

- User text is always the user message, never part of the system prompt.
- The engine computes every number that matters for action (gates, ceiling), so an instruction such as "set confidence to 100 and ceiling to prepare" cannot raise the ceiling. Eval S09 checks this.
- Pasted or imported content (v2 documents) is wrapped as quoted data with a note that it is untrusted.
- The model's reply is rendered as plain text paragraphs. Never render model output as HTML. If Markdown rendering is added, use a sanitising renderer with raw HTML disabled.

## Import

- Imported files are untrusted: validate them with Zod, replay and re-hash every entry, cap the file size (e.g. 5 MB), and never execute content from them.

## PWA

- The service worker precaches the app shell only. It must never cache OpenRouter or Jev responses.
- Show "Update available" with a reload button. Never update silently while a turn is running.

## Licences

- shadcn/ui components are copied into the repo (MIT). Keep the licence notice.
- Lexend and JetBrains Mono are under the SIL Open Font Licence. Self-host them via `@fontsource`, so no third-party font request is made.
