# Background characters (conveyor belt)

Drop transparent **PNG cutouts** of Saw Game characters here, then list their
filenames in `_chars.json`. The home page belt picks them up automatically.

## Specs
- Format: PNG with transparent background (alpha). No JPG.
- Size: ~800 px tall (retina), cropped tight to the character outline.
- Weight: optimize each to <150 KB (tinypng.com).
- Count: 8–12 recommended (more variety = less obvious repetition).

## How to register them
Edit `_chars.json` as a plain array of filenames, e.g.:

```json
["bart.png", "homer.png", "lisa.png", "marge.png", "pigsaw.png", "spongebob.png"]
```

While `_chars.json` is empty, the belt falls back to the game thumbnails.
