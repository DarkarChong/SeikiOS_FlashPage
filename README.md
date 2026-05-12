# SEIKIOS — Flash Game Preservation

> Restoring Your Gaming Memories

Non-profit Flash game preservation project. We manually patch broken AS2 code using JPEXS Free Flash Decompiler and run every game directly in the browser via [Ruffle](https://ruffle.rs) — using a **custom fork** with emulator-compatibility fixes specific to certain game engines.

**Web Page:** https://darkarchong.github.io/SeikiOS_FlashPage/

---

## How it works

1. A broken `.swf` is decompiled with JPEXS Free Flash Decompiler
2. Original AS2 bugs (e.g. broken state-machine transitions with placeholder `"XXX"` targets) are identified and patched manually
3. Emulator-compatibility patches are applied when needed (e.g. terrain walkability hooks for Inkagames engine, see below)
4. The patched game is published here, running via our Ruffle fork — no Flash Player installation required

---

## Repository structure

```
/
├── index.html              ← main catalog (lists games from _games.json)
├── _games.json             ← game metadata (id, title, thumbnail, status, bugs_fixed)
├── .nojekyll               ← required for GitHub Pages to serve underscore-prefixed files
├── assets/
│   ├── css/style.css       ← dark-maroon + gold theme
│   ├── js/catalog.js       ← async catalog loader
│   └── logo.svg            ← SEIKIOS logo + favicon
├── ruffle/                 ← self-hosted Ruffle fork bundle (~11 MB)
│   ├── ruffle.js
│   ├── core.ruffle.<hash>.js
│   ├── <hash>.wasm
│   ├── LICENSE_MIT
│   └── LICENSE_APACHE
└── games/
    └── [game-id]/
        ├── index.html      ← player + patch log
        ├── game.swf        ← patched SWF
        ├── thumbnail.png   ← catalog cover
        └── patch/          ← (planned) original AS2 sources of patched files
```

---

## Why a Ruffle fork instead of the CDN?

The upstream Ruffle CDN works for most Flash games but has two known issues that affect the **Inkagames** engine (used by Spongebob Saw Game, Bart Saw Game, Lisa Saw Game, Homer Saw Game, Batman Saw Game, Obama Ghostbusters, and many other point-and-click adventures by Inkagames):

1. **EditText `word_wrap=true` + `autosize` empty-state regression** — produces million-pixel-tall popups that cause GPU stalls and drop framerate to <1 fps. Patched in `core/src/display_object/edit_text.rs` by clamping `content_width` to a usable minimum.
2. **AVM1 `eval("path.to.button")` scope-chain resolution gap** — buttons attached dynamically via eval() paths fail to register handlers, leaving entire scene menus unresponsive. Patched in `core/src/avm1/activation.rs` by adding a `_root` fallback lookup.

The fork is hosted under `/ruffle/` in this repo so all games on SEIKIOS pick it up automatically.

There is a third, deeper engine issue (terrain walkability array built before MovieClip shapes settle in their final transforms) that affects all Inkagames. Since fixing it inside Ruffle would require restructuring its frame-execution pipeline, we patch it at the SWF level — see [the Spongebob index.html patch log](games/spongebob-saw-game/) and the frame_1 DoAction of any patched Inkagame.

---

## Adding a new game

1. Create `games/[game-id]/` with `game.swf`, `thumbnail.png`, and `index.html` (copy from `games/spongebob-saw-game/index.html` as template)
2. Edit the new `index.html`:
   - Update title, game-meta badges, and the bug list at the bottom
   - Keep the `<script src="../../ruffle/ruffle.js">` reference to the local Ruffle fork
3. Add an entry to `_games.json`:
   ```json
   {
     "id": "your-game-id",
     "title": "Your Game Title",
     "thumbnail": "games/your-game-id/thumbnail.png",
     "status": "patched",
     "bugs_fixed": 0
   }
   ```
4. For Inkagames specifically: paste the universal terrain-walkability patch into frame_1 DoAction of the SWF before saving (see the Spongebob patch as reference; the code is reusable verbatim).
5. Commit and push — GitHub Pages auto-deploys in 1-5 minutes.

---

## Tech stack

- **Vanilla HTML / CSS / JS** — no build step, no dependencies, no npm
- **Custom Ruffle fork** — built from `ruffle-rs/ruffle` with three Inkagames-specific patches
- **GitHub Pages** — free HTTPS hosting
- **JPEXS Free Flash Decompiler** — for decompiling, editing AS2, and recompiling SWFs

---

## Rights & attribution

All games belong to their original creators. SEIKIOS only hosts patched versions for preservation purposes. If you are a rights holder and want a game removed, please [open an issue](https://github.com/DarkarChong/SeikiOS_FlashPage/issues).
