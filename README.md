<p align="center">
  <img src="assets/icon.png" width="96" alt="">
</p>

<h1 align="center">Dota Chat Translator</h1>

<p align="center">
  Free, open-source, real-time translator for the Dota 2 chat.<br>
  Read what your Russian, Chinese or Peruvian teammates write, and answer them in their language.
</p>

<p align="center">
  <a href="../../releases/latest"><b>⬇ Download the latest release</b></a> ·
  <a href="README.es.md">Leer en español</a>
</p>

---

![Live chat](docs/screenshots/live.png)

## Features

- **Live translation of the in-game chat** shown in a transparent overlay on top of Dota 2, with the **portrait of the hero** who's typing and their player colour.
- **Reply in their language without leaving the game**: press **Ctrl+Enter** (team) or **Ctrl+Shift+Enter** (all) in Dota, type in the box that appears over the game, pick another language if you want, and the app translates it and sends it to Dota's chat. You can also type it in the app and paste it yourself.
- **Natural AI translation (optional)**: sign in with your ChatGPT Plus/Pro account (no key) or use a key from Gemini, Claude, ChatGPT, Groq, DeepSeek, Mistral, Grok, OpenRouter or a local model. The translation reads like a real player wrote it and understands Dota slang and the match context; Spanish from Spain and Latin American Spanish are told apart. Without AI it uses Google Translate.
- **Voice chat transcription (experimental, optional)**: everything spoken in Dota's audio is turned into text with Whisper on your own GPU and translated, only from `dota2.exe` (not Discord). You choose which languages are *not* translated.
- **Pick your languages**: translate incoming chat into any of 30+ languages; translate your messages into a fixed language or let the app detect the team's language automatically.
- **Conversation history**: every translated message is saved locally, searchable, filterable by match, exportable to CSV.
- **Knows Dota**: heroes, items and slang in English, Spanish, Russian and Chinese (`мид`, `варды`, `axe ult`, `肉山`…) are kept as game terms instead of being translated literally, and chat abbreviations (`xq`, `щас`, `idk`…) are expanded first. You can add your own.
- **Auto-updates**: when a new version is published on GitHub, the app asks whether to install it.
- **No account, no subscription, no API key needed.** It's free and always will be (AI translation is optional).
- English and Spanish interface.

| Home | History |
|---|---|
| ![Home](docs/screenshots/home.png) | ![History](docs/screenshots/history.png) |

## Quick start

1. Download **`DotaChatTranslator.exe`** from the [latest release](../../releases/latest).
2. Run it. Windows may show *"Windows protected your PC"* because the app isn't code-signed: click **More info → Run anyway** (see [Is it safe?](#is-it-safe)).
3. The app finds your Dota 2 folder and installs the integration automatically. If it can't, set the folder in **Settings → Dota 2**.
4. In Dota 2 go to **Settings → Video → Display mode** and choose **Borderless window** (the overlay can't be drawn over exclusive fullscreen).
5. **Restart Dota 2 once** so it loads the integration. When you join a match (a bot match works too), the app's status turns green: *In a match: translating chat*. Outside a match you'll see *Dota 2 open, not in a match*: that's normal, Dota only sends the chat during matches.
6. Play. Translations appear on the left side of the screen, above Dota's own chat.
7. To answer: in Dota press **Ctrl+Enter** (team chat) or **Ctrl+Shift+Enter** (all chat), type your message and press **Enter**. The app translates it, opens Dota's chat, pastes it and sends it. **Esc** cancels. Hotkeys and auto-send can be changed in **Settings → Write from the game**.

The hotkeys are registered with Windows' standard `RegisterHotKey`: the app doesn't install keyboard hooks or read what you type in the game. It only simulates keys (Enter, Ctrl+V) at the moment it sends your message, and restores your clipboard afterwards.

### Optional: natural AI translation

**No key, with your ChatGPT Plus/Pro account:** pick *ChatGPT · your Plus/Pro plan* and click **Sign in with ChatGPT**; the browser opens, you approve it and that's it. It uses your plan's allowance (you can cap the app in *Manage usage*); free ChatGPT accounts can't use it. With **OpenRouter** you can also click **Connect OpenRouter** instead of pasting a key.

Supported services with your own API key: **Gemini**, **Claude** (Anthropic), **ChatGPT** (OpenAI), **Groq**, **DeepSeek**, **Mistral**, **Grok** (xAI), **OpenRouter**, and your **own/local server** (Ollama, LM Studio…).

1. **Settings → Translation → Translation engine** → pick the service.
2. Click **Get a key**, create one and paste it. Each service keeps its own key, stored encrypted with your Windows user. The model is picked automatically; you can type another one.
3. Click **Test**: it shows the model used and how long it took. If the service fails or the quota runs out, the app falls back to Google Translate automatically.

Gemini and Groq have free plans; **Groq is the fastest**. A local model runs on your own GPU and competes with the game for it.

### Optional: voice chat (experimental)

**Settings → Voice chat → Transcribe Dota voice chat.** The first time it downloads the voice engine once (≈3 GB with an NVIDIA card: Whisper model + NVIDIA libraries; ≈0.6 GB for the CPU model). While someone talks, Whisper uses the GPU for about a second per sentence; when nobody talks it uses practically nothing.

## How it works

```
Dota 2 ──(Game State Integration, localhost)──► Dota Chat Translator ──► free translation service
                                                   │
                                                   ├─► overlay window on top of the game
                                                   └─► local history (SQLite)
```

- **Reading the chat** uses Valve's official **Game State Integration (GSI)**: the same feature used by stream overlays, Overwolf apps, STRATZ, etc. The app writes one small text file to `dota 2 beta/game/dota/cfg/gamestate_integration/` and Dota sends game events (including chat messages) to `127.0.0.1` on your PC. **The app never reads game memory, injects code or modifies game files.**
- **Translation** uses free public endpoints (Google Translate, with MyMemory as a fallback). If one of them rate-limits, the app automatically switches to the next one for a few minutes. With an AI service configured, it translates first (told it's Dota chat, with the last few messages as context) and Google is the fallback.
- **Your messages** are typed in the hotkey box (or in the app), translated, and pasted into Dota's chat.
- **Voice chat** is captured from the `dota2.exe` process only (Windows "process loopback", no virtual audio cards). A voice detector (Silero VAD) cuts out each spoken sentence and Whisper transcribes it; the announcer and the phrases Whisper invents on noise are dropped. Hero voice lines are transcribed too. Languages ticked in *Don't translate these languages* aren't sent to the translator.
- **The overlay** is a separate transparent window that lets mouse clicks pass through.
- **Hero portraits**: GSI only tells *which player* (0–9) wrote a message, not their hero. The top bar of Dota's HUD shows the heroes in that same order, so when a message arrives the app crops that small portrait from the Dota window. It's processed locally and stored only in your history. Positions scale with your resolution automatically; if they don't fit your screen (ultrawide, 4:3…), open **Settings → Overlay → Calibrate portraits**, capture Dota's top bar and move the sliders until the boxes fit the portraits; changes apply live.

## Is it safe?

- **VAC / bans.** The app only uses Valve's official GSI feature, a normal Windows overlay window and screen/audio capture like recording software. It doesn't hook or log your keyboard; it only presses Enter/Ctrl+V when you send a message from the hotkey box. It doesn't touch the game process. That said, this project is **not affiliated with or endorsed by Valve**; use it at your own risk.
- **"Windows protected your PC" / antivirus warnings.** The `.exe` isn't code-signed (certificates cost money every year), and single-file Python apps built with PyInstaller are sometimes flagged by antivirus heuristics as false positives. You can:
  - check the file against the `SHA256SUMS.txt` published with each release: `Get-FileHash .\DotaChatTranslator.exe` in PowerShell;
  - read the source code: every release is built automatically by [GitHub Actions](.github/workflows/release.yml) from this repository;
  - or [run/build it from source](#build-from-source).
- **Privacy.** There is no telemetry and no account. The **text of chat messages is sent to the translation service** (Google Translate / MyMemory, or the AI service you configure; some free plans, such as Gemini's, may use the texts to improve their models), nothing else. Voice is transcribed on your PC; no audio leaves it. Hero portraits are captured and kept locally. On startup the app asks GitHub's public API whether there's a new version (can be turned off in Settings). History and settings are stored only on your PC.

## Settings and data

Everything is stored in `%APPDATA%\DotaChatTranslator\` (Settings → *Open data folder*):

| File | Contents |
|---|---|
| `config.json` | Your settings |
| `history.db` | Conversation history (SQLite) |
| `glossary.json` | *(optional)* your own slang entries, same format as [`app/glossary.json`](app/glossary.json) |
| `app.log` | Log file, useful when reporting bugs |

### Uninstall

1. In the app: **Home → Remove integration** (deletes the file the app added to Dota's `cfg` folder).
2. Delete `DotaChatTranslator.exe` and the `%APPDATA%\DotaChatTranslator` folder.

## Troubleshooting

| Problem | Fix |
|---|---|
| Status stays on *Waiting for Dota 2* | Restart Dota 2 after the integration is installed. Check the folder in Settings → Dota 2. |
| The overlay doesn't show | Use **Borderless window** in Dota and check *Show in-game overlay* is on. |
| Voice chat isn't transcribed | Check the status in Settings → Voice chat says *Listening to Dota 2*, and that the language isn't ticked in *Don't translate these languages*. |
| Messages appear untranslated | The free translation services may be rate-limiting; the app retries with another provider. Check `app.log`. |
| *Could not open port 53123* | Another copy of the app is already running, or another program uses that port: change it in Settings → Dota 2 → Local port and click *Install integration* again. |

## Limitations

- **Windows only**, Dota 2 in borderless or windowed mode.
- GSI identifies the sender only by **player colour** (slot), not by name or hero; the hero portrait is taken from the screen, so it needs Dota's top bar to be visible (calibrated on 16:9; other aspect ratios may need a quick calibration in Settings).
- Free translation services are unofficial endpoints: quality is good but not perfect, and they could change or limit usage at any time.

## Build from source

Requires Windows and Python 3.10+.

```powershell
git clone https://github.com/Rucerdo/dota-translator.git
cd dota-translator
py -m pip install -r requirements.txt
py run.py            # run the app
.\build.bat          # build dist\DotaChatTranslator.exe
```

Project layout:

```
app/
  gui.py          desktop window (CustomTkinter)
  core.py         engine: wires GSI, translation, overlay, history
  gsi.py          local Game State Integration server (chat events)
  translator.py   free translation with provider fallback + Dota glossary
  overlay.py      transparent click-through in-game overlay
  ai/             optional AI translation: Gemini, Claude, OpenAI-compatible services, Sign in with ChatGPT
  winkeys.py      compose hotkeys (RegisterHotKey) and sending to Dota's chat
  portraits.py    hero portraits from Dota's top bar
  updater.py      auto-updates from GitHub Releases
  voice/          voice chat: process audio capture, voice detector, Whisper engine
  history.py      SQLite history
  dota.py         Dota 2 folder detection, GSI config install/remove
  i18n.py         UI strings (en/es) and language list
  glossary.json   Dota slang dictionary
run.py            entry point
```

### Releasing a new version

1. Update `__version__` in `app/__init__.py` and `CHANGELOG.md`.
2. Commit, then tag and push: `git tag v1.0.1 && git push origin v1.0.1`.
3. GitHub Actions builds the `.exe` and publishes the release with its checksum.

## Contributing

Issues and pull requests are welcome, especially:

- **Slang**: add entries to [`app/glossary.json`](app/glossary.json) for your language.
- **UI translations**: add a language to `STRINGS` in [`app/i18n.py`](app/i18n.py).

## License

[MIT](LICENSE). Dota 2 is a registered trademark of Valve Corporation. This project is not affiliated with Valve.
