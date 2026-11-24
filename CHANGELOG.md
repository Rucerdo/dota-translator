# Changelog

## [1.2.1] - 2026-11-25

### Changed
- The language you pick in the Ctrl+Enter box is remembered as your default language for your messages, so you
  don't need to open the app to change it.
- Clearer connection status: it now says whether Dota 2 is closed, open but not in a match, or in a match
  (Dota only sends the chat during matches).

## [1.2.0] - 2026-11-24

### Added
- **AI translation with many services**: Gemini, Claude, ChatGPT, Groq, DeepSeek, Mistral, Grok, OpenRouter and
  your own/local server (Ollama, LM Studio…). Each service keeps its own key, encrypted with your Windows user.
  The model is picked automatically, and the **Test** button shows the model and the latency. If the AI fails
  or runs out of quota, the app falls back to Google Translate.
- **Sign in with ChatGPT**: ChatGPT Plus/Pro users can sign in through the browser and translate using their
  plan, without an API key. **Connect OpenRouter** creates an OpenRouter key from the browser.
- **Spanish from Spain and Latin American Spanish** as separate languages (with AI translation).
- **Write from the game**: press Ctrl+Enter (team) or Ctrl+Shift+Enter (all) in Dota, type in the box over the
  game, optionally pick another language, and the message is translated and sent to Dota's chat. It uses
  `RegisterHotKey` (no keyboard hooks) and restores the clipboard afterwards.
- **Voice chat transcription (experimental)**: Dota's own audio is captured with Windows process loopback (no
  virtual audio cards). Speech is cut into phrases with Silero VAD and transcribed locally with Whisper
  (large-v3-turbo on NVIDIA GPUs). The voice engine is a separate, one-time download.
- **Language filter for voice**: you choose which spoken languages are *not* translated.

### Changed
- The AI prompt now handles Dota slang by context, so the hand-made glossary is only used for Google Translate.
- Sending your own translated messages now works through the hotkey box above.

### Removed
- The `keyboard` dependency. It could leave the Alt key stuck in game.

## [1.1.0] - 2026-11-23

### Added
- **Hero portraits**: the portrait of the hero who is typing appears next to each message in the overlay, the live
  chat and the history. It's cropped from Dota's top bar (GSI only provides the player slot) and greyed out if the
  hero is dead. Stored with each message in the history.
- **Live portrait calibrator** (Settings → Overlay → Calibrate portraits): captures Dota's top bar, draws the 10
  boxes on top and lets you move them with sliders; changes apply instantly. Positions scale with the resolution
  automatically (1080p, 1440p, 4K), the calibrator covers ultrawide, 16:10 or 4:3 screens.
- **Automatic updates** from GitHub Releases: on startup the app checks for a newer version, shows the release
  notes and offers to update, skip that version or remind later. Downloads with a progress bar, verifies the
  SHA-256 and replaces itself. Can be turned off in Settings.
- **Hero names** in the glossary (English, Russian and Chinese names and nicknames): `axe ult doom` no longer
  becomes "hacha ult fatalidad".
- **Chinese glossary** (`肉山` → Roshan, `真眼` → Sentry Ward, `屠夫` → Pudge…), matched without word boundaries.
- **Word stems** in the glossary (`вард*` covers варды, вардов, вардами…; `wardear`, `pusheamos`…).
- **Abbreviation expansion** before translating, so they come out in the right language: `xq` → porque,
  `щас` → сейчас, `спс` → спасибо, `го` → давай, `idk` → I don't know…

### Fixed
- Glossary entries that broke normal sentences: `se` (turned "no sé" into "Silver Edge"), `as`, `off`, `safe`,
  `miss`, `force`, `phase`, `bots`, `назад`, `даст`, among others. Wrong mappings such as `стиков` → Magic Wand.
- The new version waits for the previous one to release the GSI port when restarting after an update.

## [1.0.0] - 2026-11-23

First public release.

- Real-time translation of Dota 2 chat through Valve's official Game State Integration (GSI).
- In-game overlay: transparent, click-through, coloured by player slot, optional original text.
- Ctrl+Enter in Dota chat translates your message into the team's language before sending it.
- Desktop app with Home, Live chat, History and Settings screens (English / Spanish).
- Choice of incoming and outgoing languages (30+ languages, automatic team-language detection).
- Local conversation history (SQLite) with search, match filter and CSV export.
- Free translation without API keys, with automatic fallback between providers when one rate-limits.
- Dota slang glossary that users can extend.
- One-click install/removal of the GSI integration; automatic Dota 2 folder detection.
