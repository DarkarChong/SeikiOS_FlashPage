# SEIKIOS — Flash Game Preservation

> Restoring Your Gaming Memories

Non-profit Flash game preservation project. We manually patch broken AS2 code using JPEXS Free Flash Decompiler and run every game directly in the browser via [Ruffle](https://ruffle.rs).

Web Page: https://darkarchong.github.io/SeikiOS_FlashPage/

## How it works

1. A broken `.swf` is decompiled with JPEXS Free Flash Decompiler
2. AS2 bugs are identified and patched manually
3. The patched game is published here, running via Ruffle (no Flash required)

## Structure

```
/
├── index.html              ← main catalog
├── _games.json             ← game metadata
├── assets/
│   ├── css/style.css
│   └── js/catalog.js
└── games/
    └── [game-id]/
        ├── index.html      ← player + patch log
        ├── game.swf
        ├── thumbnail.png
        └── patch/          ← corrected AS2 scripts
```

## Adding a game

1. Create `games/[game-id]/` with `game.swf`, `thumbnail.png`, and `index.html` (copy the template)
2. Add an entry to `_games.json`
3. Fill in the bug list inside the game's `index.html`

## Rights

All games belong to their original creators. SEIKIOS only hosts patched versions for preservation purposes. If you are a rights holder and want a game removed, please open an issue.

## Tech

- Vanilla HTML / CSS / JS — no build step, no dependencies
- [Ruffle](https://ruffle.rs) — open-source Flash emulator
- GitHub Pages — free HTTPS hosting
