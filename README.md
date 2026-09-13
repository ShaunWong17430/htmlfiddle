# HTML Fiddle

<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

Edit an existing HTML file **visually in your browser**: double-click to change copy,
tweak styles in the panel, switch to Preview to test interactions, hit Save to write
back to the same file on disk.

```
Double-click start-workbench.bat  →  pick a .html  →  edit in the browser  →  Save
```

No Node. No npm. No build step. One Python interpreter is the only dependency.

---

## ⚠️ This is not the upstream project

HTML Fiddle is a **downstream derivative of
[alienzhou/html-workbench](https://github.com/alienzhou/html-workbench)**
(pinned at commit `8418087`), maintained by
[ShaunWong17430](https://github.com/ShaunWong17430).

Upstream is designed as a first-class **DeepSeek Harness plugin** — the editor lives in
the DSH sidebar and is driven by an agent. HTML Fiddle does the opposite: it **strips the
plugin shell** so the same editor runs standalone on a machine with no DSH, no Node and
no npm, launched by double-clicking a `.bat`.

- Upstream bugs and feature requests → [alienzhou/html-workbench](https://github.com/alienzhou/html-workbench)
- Launcher, entry scripts, Python detection, standalone-run issues → [issues here](https://github.com/ShaunWong17430/htmlfiddle/issues)

Provenance and per-file hashes: **[UPSTREAM.md](UPSTREAM.md)**. Licensing and attribution: **[NOTICE](NOTICE)**.

*Heads-up: the UI, the log output and `docs/` are currently Chinese-only. The CLI flags
and file paths are not localized.*

### Relationship to the DSH plugin

The two are **fully independent and can run side by side**:

| | DSH plugin | HTML Fiddle |
| --- | --- | --- |
| Default port | `4317` | `4318` (`--port` to change) |
| Where the UI lives | DSH right sidebar | Your own browser tab |
| How it starts | Auto, when DSH loads the plugin | Double-click `start-workbench.bat` |
| Selected copy → AI | Injects a chip into the chat input | Copies a selection Markdown to the **clipboard** |
| Where files come from | Tracks html files the agent just wrote | Whatever file you pick or drag |

The port is deliberately different, so `stop-workbench.bat` will not kill the service DSH
started (verified: after stopping this project's service, DSH's 4317 stays healthy).

The upstream front-end already ships a fallback for "not inside an iframe", so the **only**
capability lost by leaving DSH is turning selected copy into a chat chip — the clipboard
replaces it. Everything else (editing, saving, preview, style panel, auto-refresh on external
changes) comes from the engine and behaves identically standalone.

---

## Quick start

**Option 1 — double-click**

Double-click `start-workbench.bat`. A menu lists recently opened files; pick a number, or
press `n` to create a new one.

**Option 2 — drag and drop**

Drag any `.html` file onto `start-workbench.bat`. It opens directly — the file can live
anywhere, not just in `pages/`.

**Option 3 — command line**

```bat
start-workbench.bat "D:\work\report.html"        :: open a specific file
start-workbench.bat --new landing                 :: create pages\landing.html and open it
start-workbench.bat --list                        :: list recent files only
start-workbench.bat --status                      :: health check: service + offline assets
stop-workbench.bat                                :: stop the background service
```

Closing the browser does **not** stop the service (so you can reopen quickly). To stop it,
run `stop-workbench.bat`.

On macOS / Linux use `start-workbench.command` (may need `chmod +x` the first time).

---

## Repository layout

```
htmlfiddle/
├─ start-workbench.bat      Windows entry point (double-click / drag & drop)
├─ stop-workbench.bat       Stops the background service
├─ start-workbench.command  macOS / Linux entry point
├─ scripts/
│  ├─ launcher.py           ★ Original to this project: file picker, service bootstrap,
│  │                          browser launch, recent files, status / stop
│  ├─ find-python.bat       ★ Original: interpreter probing (actually runs each candidate,
│  │                          skips the Microsoft Store stub)
│  └─ workbench.py          ↑ Upstream engine (alienzhou/html-workbench), one compat patch
├─ assets/
│  └─ workbench.html        ↑ Upstream GrapesJS front-end, unmodified
├─ vendor/                  GrapesJS 0.23.4 offline bundle (BSD-3-Clause; hashes match
│                           the values hardcoded in the engine)
├─ pages/                   Default directory for new files (includes example.html)
├─ logs/                    Runtime logs (not committed)
├─ state/                   Recent-file record / temp handoff files (not committed)
├─ docs/                    Web walkthrough index.html + architecture diagram
├─ LICENSE                  MIT — covers only the original parts of this project
├─ NOTICE                   Third-party attribution and license status
└─ UPSTREAM.md              Upstream provenance, hashes, patch, upgrade steps
```

The launcher only calls the engine's CLI (`serve` / `open` / `health` / `stop`) and never
reaches into its internals.

---

## Requirements and offline behavior

- **Python ≥ 3.9** (same as the engine; standard library only). Python 3.13 works out of the box.
  The entry script locates an interpreter itself: `py -3` → every `python`/`python3` on PATH →
  common install locations (miniconda / anaconda / Program Files), and it **actually executes
  each candidate** to verify it, so an interpreter that merely "exists" can't fool it.
  See UPSTREAM.md §4.
- **No network needed on first run.** GrapesJS is vendored in `vendor/`, and its hashes are
  byte-identical to the expected values hardcoded in the engine, so the engine's own check
  passes and it uses the local files. Confirm with `--status`:

  ```
  GrapesJS assets (offline cache):
    grapes.min.js        1124 KB  present
    grapes.min.css         60 KB  present
  ```

- **On a machine without Python:** drop a Windows embeddable Python into `runtime/` and make
  the `.bat` prefer it. **A single-file exe is deliberately not provided** — the launcher
  spawns `scripts/workbench.py` as a subprocess, and once frozen with PyInstaller
  `sys.executable` no longer points at Python, which needs real argv-dispatch rework.
  Shipping a broken exe helps nobody.

---

## Security and limits

- The service binds to **`127.0.0.1` only** — it is not exposed to the LAN. It has **no
  authentication**, though: any process on your machine can read and write the html file you
  have open via `http://127.0.0.1:4318`. Don't forward the port, and don't leave it running
  on an untrusted multi-user machine.
- The engine can open `.html` at **any path**, not just under `pages/`.
- Saves are guarded by a `revision` check. If the file changed on disk while you were editing,
  the save is **rejected** rather than overwriting. Verified:

  ```
  PUT /api/document (stale baseRevision)
  → 409 REVISION_CONFLICT / file modified externally, latest version not overwritten.
  ```

- Only `.html` files are accepted (engine limitation).
- On save, the engine injects a `<style data-grapesjs-overrides>` block into `<head>` to carry
  styles produced by the style panel. This is existing upstream behavior, not a bug.

---

## Troubleshooting

Start with the health check:

```bat
start-workbench.bat --status
```

| Symptom | Fix |
| --- | --- |
| Double-click shows only `[exit code: 9009]` | Legacy symptom of "Python not found correctly"; fixed. If it persists, the zero-byte Microsoft Store `python.exe` stub precedes the real interpreter on PATH and the fallbacks found nothing — install a real Python. Diagnose: if the first result of `where python` points at `...\AppData\Local\Microsoft\WindowsApps\`, that's it |
| `No usable Python 3.9+ found` | No usable Python 3.9+ on the machine. Install Python with "Add python.exe to PATH" checked, or install Miniconda. The entry script explicitly skips the Store stub and prints this guidance |
| Port already in use | Use another port: `start-workbench.bat --port 4399 "D:\x\a.html"` |
| Browser opens blank / errors | Check `logs\workbench-<port>.log`; confirm `--status` reports both the engine script and the front-end page as present |
| `VENDOR_DOWNLOAD_FAILED` | `vendor/` was deleted or the hashes don't match (the engine verifies byte-for-byte). Restore the two files, or let it download them |
| Service won't stop | Run `stop-workbench.bat`; if another program owns the port, switch ports or end that process manually |
| Skip the launcher entirely | `python scripts\workbench.py open "D:\x\a.html" --vendor-cache vendor --log-dir logs` — equivalent |

Antivirus / firewall may flag "starts a local service and opens a browser". Allow it —
loopback address only.

---

## License

**This repository is not under a single license. Do not treat it as MIT as a whole.**

| Part | License | Notes |
| --- | --- | --- |
| Code original to this project (launcher, entry scripts, docs, example page) | **MIT** | See [LICENSE](LICENSE) |
| `scripts/workbench.py`, `assets/workbench.html` | **No LICENSE file upstream — but the author himself published this same code on npm as MIT** | From alienzhou/html-workbench. The two facts conflict; this project does not claim MIT on the author's behalf, treats the files as MIT in practice, and preserves full attribution |
| `vendor/grapes.min.js`, `vendor/grapes.min.css` | **BSD-3-Clause** | GrapesJS 0.23.4, see [vendor/LICENSE-grapesjs.txt](vendor/LICENSE-grapesjs.txt) |

Full attribution, per-file SHA-256, and guidance on how to treat the upstream-derived files:
**[NOTICE](NOTICE)**. Technical lineage, the patch diff, and how to follow upstream upgrades:
**[UPSTREAM.md](UPSTREAM.md)**.
