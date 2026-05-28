#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_inkagame.py - Automated Inkagames Saw Game patcher for SEIKIOS

Pipeline:
  1. validate     - Verify inputs (SWF, JPEXS, vault structure)
  2. export       - Run JPEXS CLI to export AS2 scripts
  3. discover     - Parse AS2 to find minified names (CHECK_FN, OBJ_SCENE, RECT, etc.)
  4. patch        - Read template, substitute placeholders, build patched DoAction.as
  5. inject       - Use JPEXS -replace to write patched SWF
  6. deploy       - Copy SWF + thumbnail, generate index.html, update _games.json + sitemap.xml

Usage:
  python patch_inkagame.py \\
    --swf "C:/path/to/homer.swf" \\
    --id homer-saw-game \\
    --title "Homer Simpson Saw Game" \\
    --year 2010 \\
    --thumbnail "C:/path/to/thumb.png"

Optional:
  --vault <path>      Override vault root (default: parent of this script's tools/ dir)
  --jpexs <path>      Override JPEXS path (default: C:/Program Files (x86)/FFDec/ffdec-cli.exe)
  --dry-run           Print what would happen, don't write
  --skip-deploy       Stop after SWF patching, don't touch site files
  --discover-only     Just print discovered names and exit (debugging)
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ============================================================================
# Defaults
# ============================================================================
DEFAULT_JPEXS = r"C:\Program Files (x86)\FFDec\ffdec-cli.exe"

# Vault root = parent of this script's directory (tools/)
VAULT_ROOT = Path(__file__).resolve().parent.parent

# Anchor strings/patterns we look for in AS2 scripts
ANCHOR_WALKABILITY_TRACE = "no es caminable según el arreglo de terreno"


# ============================================================================
# Logging helpers
# ============================================================================
def log(msg):
    print(f"[*] {msg}", flush=True)


def ok(msg):
    print(f"[OK] {msg}", flush=True)


def warn(msg):
    print(f"[!] {msg}", flush=True)


def fatal(msg, code=1):
    print(f"[FATAL] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ============================================================================
# Phase 1: Validate
# ============================================================================
def validate_inputs(args):
    swf = Path(args.swf).resolve()
    if not swf.is_file():
        fatal(f"SWF not found: {swf}")

    thumb = Path(args.thumbnail).resolve() if args.thumbnail else None
    if thumb and not thumb.is_file():
        fatal(f"Thumbnail not found: {thumb}")

    jpexs = Path(args.jpexs).resolve()
    if not jpexs.is_file():
        fatal(f"JPEXS not found at: {jpexs}\nInstall from https://github.com/jindrapetrik/jpexs-decompiler/releases")

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        fatal(f"Vault root not a directory: {vault}")
    if not (vault / "_games.json").is_file():
        fatal(f"Vault doesn't look right - missing _games.json: {vault}")
    if not (vault / "sitemap.xml").is_file():
        fatal(f"Vault doesn't look right - missing sitemap.xml: {vault}")

    template = vault / "tools" / "patch_template.as"
    if not template.is_file():
        fatal(f"Patch template not found: {template}")

    # Validate id format (kebab-case)
    if not re.match(r"^[a-z][a-z0-9-]+$", args.id):
        fatal(f"Invalid --id '{args.id}': must be kebab-case (lowercase + digits + hyphens, start with letter)")

    ok(f"Inputs validated. Vault: {vault}")
    return {
        "swf": swf,
        "thumb": thumb,
        "jpexs": jpexs,
        "vault": vault,
        "template": template,
    }


# ============================================================================
# Phase 2: Export AS2 scripts via JPEXS
# ============================================================================
def export_scripts(jpexs, swf, out_dir):
    log(f"Exporting scripts from {swf.name}...")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(jpexs), "-export", "script", str(out_dir), str(swf)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        fatal(f"JPEXS export failed (code {result.returncode}):\n{result.stderr}")
    # JPEXS prints export progress + final "OK" - look for it
    if "OK" not in result.stdout.splitlines()[-1:]:
        warn(f"JPEXS finished but final 'OK' not seen. Stderr tail:\n{result.stderr[-500:]}")
    scripts_dir = out_dir / "scripts"
    if not scripts_dir.is_dir():
        fatal(f"Expected scripts/ directory not created: {scripts_dir}")
    ok(f"Exported to {scripts_dir}")
    return scripts_dir


# ============================================================================
# Phase 3: Discover minified names
# ============================================================================
def grep_files(scripts_dir, anchor):
    """Find files containing the anchor string. Returns list of Path."""
    matches = []
    for as_file in scripts_dir.rglob("*.as"):
        try:
            text = as_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if anchor in text:
            matches.append(as_file)
    return matches


def discover_check_fn_and_terrain(walkability_file):
    """
    Find the global check function name and terrain array name.
    Pattern: if(!_root.xyzNNN(this.xyzMMM,...))  with the 'no es caminable' trace right after.
    Returns (check_fn, terrain_array).
    """
    text = walkability_file.read_text(encoding="utf-8", errors="replace")
    # Look for the specific pattern near the anchor trace.
    # Allow some flexibility: _root.xyz<N>(this.xyz<N>,...
    pattern = re.compile(
        r"if\s*\(\s*!\s*_root\.(xyz\d+)\s*\(\s*this\.(xyz\d+)\s*,"
    )
    matches = pattern.findall(text)
    if not matches:
        fatal(
            f"Could not find check-fn pattern `if(!_root.xyzNNN(this.xyzMMM,...))` in {walkability_file}.\n"
            "The walkability function structure may differ in this game."
        )
    # If multiple, prefer one near the anchor trace
    if len(set(matches)) > 1:
        # Pick the one closest to the trace string
        idx_anchor = text.find(ANCHOR_WALKABILITY_TRACE)
        best = None
        best_dist = float("inf")
        for m in pattern.finditer(text):
            d = abs(m.start() - idx_anchor)
            if d < best_dist:
                best_dist = d
                best = m.groups()
        return best
    return matches[0]


def discover_scene_clip(walkability_file):
    """
    Find the scene-clip name (e.g. xyz122 in Lisa, xyz124 in Spongebob).
    Pattern: this.xyzNNN.globalToLocal( or this.xyzNNN.localToGlobal( or this.xyzNNN.mcWalkRange
    """
    text = walkability_file.read_text(encoding="utf-8", errors="replace")
    patterns = [
        r"this\.(xyz\d+)\.globalToLocal\b",
        r"this\.(xyz\d+)\.localToGlobal\b",
        r"this\.(xyz\d+)\.mcWalkRange\b",
    ]
    candidates = []
    for p in patterns:
        candidates.extend(re.findall(p, text))
    if not candidates:
        # Fallback: maybe inside `with(this)` block - check unqualified
        # Find `with(this)` blocks and search inside them
        for m in re.finditer(r"with\s*\(\s*this\s*\)\s*\{", text):
            # Take next ~500 chars
            block = text[m.end():m.end() + 1500]
            candidates.extend(re.findall(r"\b(xyz\d+)\.mcWalkRange\b", block))
            candidates.extend(re.findall(r"\b(xyz\d+)\.globalToLocal\b", block))
            candidates.extend(re.findall(r"\b(xyz\d+)\.localToGlobal\b", block))
    if not candidates:
        fatal(f"Could not find scene-clip name (xyzNNN.mcWalkRange) in {walkability_file}")
    # Most common = answer
    from collections import Counter
    return Counter(candidates).most_common(1)[0][0]


def discover_index_calc(scripts_dir):
    """
    Find the index-calculation function (xyz1418 equivalent).
    Pattern:
        function xyzNNN(x, y, xyz<obj>) {
            xyz<obj>.xyz<row_or_col> = Math.floor((x - <RECT_REF>.xMin) / <CELL_W_REF>);
            xyz<obj>.xyz<col_or_row> = Math.floor((y - <RECT_REF>.yMin) / <CELL_H_REF>);
        }
    Returns dict with: obj_scene (or None), rect, cell_w_ref, cell_h_ref.
    cell_w_ref and cell_h_ref are FULL references (may include "xyz.xyz" or just "xyz")
    """
    # Regex: match the body. The function name can be anywhere.
    pattern = re.compile(
        r"Math\.floor\s*\(\s*\(\s*\w+\s*-\s*([\w.]+)\.xMin\s*\)\s*/\s*([\w.]+)\s*\)\s*;"
        r"\s*\w+\.\w+\s*="
        r"\s*Math\.floor\s*\(\s*\(\s*\w+\s*-\s*([\w.]+)\.yMin\s*\)\s*/\s*([\w.]+)\s*\)\s*;",
        re.DOTALL,
    )
    for as_file in scripts_dir.rglob("*.as"):
        try:
            text = as_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = pattern.search(text)
        if not m:
            continue
        rect_ref_x, cell_w_ref, rect_ref_y, cell_h_ref = m.groups()
        if rect_ref_x != rect_ref_y:
            warn(f"RECT ref mismatch: xMin from `{rect_ref_x}`, yMin from `{rect_ref_y}` - using `{rect_ref_x}`")
        # Split rect_ref to get OBJ_SCENE and RECT name (e.g. "xyz111.xyz1372" -> obj=xyz111, rect=xyz1372)
        parts = rect_ref_x.split(".")
        if len(parts) == 2:
            obj_scene = parts[0]
            rect = parts[1]
        elif len(parts) == 1:
            # No objScene prefix - rect is a global var? unusual
            obj_scene = None
            rect = parts[0]
        else:
            fatal(f"Unexpected RECT ref structure: {rect_ref_x}")
        log(f"Index-calc found in {as_file.name}: obj_scene={obj_scene}, rect={rect}, cell_w_ref={cell_w_ref}, cell_h_ref={cell_h_ref}")
        return {
            "obj_scene": obj_scene,
            "rect": rect,
            "cell_w_ref": cell_w_ref,
            "cell_h_ref": cell_h_ref,
            "source_file": str(as_file),
        }
    fatal("Could not find index-calc function (Math.floor pattern). Inkagame structure may differ.")


def discover_names(scripts_dir):
    """Run all discovery and return a dict with all minified names."""
    log("Discovering minified names...")

    walk_files = grep_files(scripts_dir, ANCHOR_WALKABILITY_TRACE)
    if not walk_files:
        fatal(f"Anchor string not found in any AS file: '{ANCHOR_WALKABILITY_TRACE}'")
    if len(walk_files) > 1:
        warn(f"Anchor found in {len(walk_files)} files - using first: {walk_files[0].name}")
    walk_file = walk_files[0]
    log(f"Walkability anchor found in: {walk_file.relative_to(scripts_dir)}")

    check_fn, terrain_array = discover_check_fn_and_terrain(walk_file)
    log(f"  check_fn       = {check_fn}")
    log(f"  terrain_array  = {terrain_array}")

    scene_clip = discover_scene_clip(walk_file)
    log(f"  scene_clip     = {scene_clip}")

    idx = discover_index_calc(scripts_dir)
    obj_scene = idx["obj_scene"]
    rect = idx["rect"]
    cell_w_ref = idx["cell_w_ref"]
    cell_h_ref = idx["cell_h_ref"]
    log(f"  obj_scene      = {obj_scene}")
    log(f"  rect           = {rect}")
    log(f"  cell_w_ref     = {cell_w_ref}")
    log(f"  cell_h_ref     = {cell_h_ref}")

    if obj_scene is None:
        fatal("Discovered obj_scene = None. Patch template requires an objScene reference.")

    # Build the cell width/height refs as they'll appear inside _loc6_ = _root.obj_scene
    # In the patch, _loc6_ IS _root.obj_scene
    # If discovered ref was "xyz111.xyz1392" -> use "_loc6_.xyz1392"
    # If discovered ref was "_root.xyz1243" or "xyz1243" -> use as-is (root-scoped)
    def transform_for_patch_scope(ref, obj_scene):
        """Transform a ref discovered in xyz1418's scope to the patch's _loc6_ scope."""
        if ref.startswith(f"{obj_scene}."):
            tail = ref[len(obj_scene) + 1 :]
            return f"_loc6_.{tail}"
        # Otherwise treat as root-scoped (with or without _root. prefix)
        if not ref.startswith("_root."):
            return f"_root.{ref}"
        return ref

    cell_w_patch = transform_for_patch_scope(cell_w_ref, obj_scene)
    cell_h_patch = transform_for_patch_scope(cell_h_ref, obj_scene)

    # For _rebuildTerrain, the equivalent is the full path expression
    def rebuild_form(ref, obj_scene):
        if ref.startswith(f"{obj_scene}."):
            tail = ref[len(obj_scene) + 1 :]
            return f"_root.{obj_scene}.{tail}"
        if not ref.startswith("_root."):
            return f"_root.{ref}"
        return ref

    rebuild_cell_w = rebuild_form(cell_w_ref, obj_scene)
    rebuild_cell_h = rebuild_form(cell_h_ref, obj_scene)

    return {
        "CHECK_FN": check_fn,
        "OBJ_SCENE": obj_scene,
        "SCENE_CLIP": scene_clip,
        "TERRAIN_ARRAY": terrain_array,
        "RECT": rect,
        "CELL_W_REF": cell_w_patch,
        "CELL_H_REF": cell_h_patch,
        "REBUILD_CELL_W": rebuild_cell_w,
        "REBUILD_CELL_H": rebuild_cell_h,
    }


# ============================================================================
# Phase 4: Generate patch
# ============================================================================
def find_frame1_doaction(scripts_dir):
    """Find frame_1/DoAction.as (the entry point we'll patch)."""
    candidate = scripts_dir / "frame_1" / "DoAction.as"
    if candidate.is_file():
        return candidate
    # Fallback: any DoAction.as in frame_1
    f1 = scripts_dir / "frame_1"
    if f1.is_dir():
        # Pick the one with the most likely content (small, has `xyz1 = false` or `xyz2 = false`)
        for f in sorted(f1.iterdir()):
            if f.suffix == ".as":
                content = f.read_text(encoding="utf-8", errors="replace")
                if re.search(r"^xyz\d+ = (true|false);", content.strip()):
                    return f
    fatal(f"Could not find frame_1/DoAction.as in {scripts_dir}")


def generate_patch(template_path, names, orig_init):
    """Read template, substitute {{KEY}} placeholders, return patched AS source."""
    template = template_path.read_text(encoding="utf-8")
    # Remove the comment block at top (lines starting with //)
    # Actually keep them - JPEXS strips comments on recompile anyway, so harmless
    patched = template
    substitutions = {
        "ORIG_INIT": orig_init.strip(),
        **names,
    }
    for key, value in substitutions.items():
        patched = patched.replace(f"{{{{{key}}}}}", value)
    # Sanity check - no placeholders left
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", patched)
    if leftover:
        fatal(f"Patch template still has unresolved placeholders: {set(leftover)}")
    return patched


# ============================================================================
# Phase 5: Inject patch into SWF
# ============================================================================
def inject_patch(jpexs, swf_in, swf_out, patched_as_file):
    log(f"Injecting patch into SWF...")
    cmd = [
        str(jpexs),
        "-replace",
        str(swf_in),
        str(swf_out),
        r"\frame_1\DoAction",
        str(patched_as_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        fatal(
            f"JPEXS replace failed (code {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}\n"
            f"Patched AS:\n{patched_as_file}"
        )
    if not swf_out.is_file():
        fatal(f"JPEXS replace completed but output SWF not created: {swf_out}")
    ok(f"Patched SWF: {swf_out} ({swf_out.stat().st_size} bytes)")


# ============================================================================
# Phase 6: Deploy
# ============================================================================
def deploy_swf(patched_swf, vault, game_id):
    game_dir = vault / "games" / game_id
    game_dir.mkdir(parents=True, exist_ok=True)
    target = game_dir / "game.swf"
    if target.exists():
        backup = game_dir / "game.swf.backup_predebug"
        if not backup.exists():
            shutil.copy2(target, backup)
            log(f"Backed up existing SWF to {backup.name}")
    shutil.copy2(patched_swf, target)
    ok(f"SWF deployed: {target}")
    return game_dir


def deploy_thumbnail(thumb, game_dir):
    if not thumb:
        warn("No thumbnail provided - skipping (you'll need to add one manually)")
        return
    target = game_dir / "thumbnail.png"
    shutil.copy2(thumb, target)
    ok(f"Thumbnail deployed: {target}")


def generate_index_html(vault, game_id, title, year):
    """Clone the most recent game's index.html and substitute."""
    template_game = vault / "games" / "lisa-saw-game" / "index.html"
    src_id = "lisa-saw-game"
    src_title_long = "Lisa Simpson Saw Game"
    src_character = "lisa"  # first word of src_title_long, lowercased

    if not template_game.is_file():
        template_game = vault / "games" / "bart-saw-game-1" / "index.html"
        src_id = "bart-saw-game-1"
        src_title_long = "Bart Simpson Saw Game"
        src_character = "bart"
    if not template_game.is_file():
        fatal(f"No template index.html found in games/lisa-saw-game or games/bart-saw-game-1")

    content = template_game.read_text(encoding="utf-8")
    src_year = "2010"

    # Derive new character first-name (lowercase) from the new title.
    # E.g. "Homer Simpson Saw Game" -> "homer"; "Spongebob Saw Game" -> "spongebob"
    new_character = title.split()[0].lower() if title else game_id.split("-")[0]

    # Substitute (order matters: more specific first, less specific last)
    content = content.replace(src_id, game_id)
    content = content.replace(src_title_long, title)

    # Case-preserving character substitution for keywords/description text
    # Match the source character as a standalone word (not inside other words)
    # so we don't accidentally replace e.g. "license" if src_character were "lic"
    def replace_word_keep_case(text, old, new):
        # Replace 'old' (case-insensitive whole-word) with 'new' preserving case style:
        #  - Old fully lowercase -> new lowercase
        #  - Old Capitalized      -> new Capitalized
        #  - Old UPPERCASE        -> new UPPERCASE
        def repl(m):
            matched = m.group(0)
            if matched.isupper():
                return new.upper()
            if matched[0].isupper():
                return new.capitalize()
            return new.lower()
        return re.sub(rf"\b{re.escape(old)}\b", repl, text, flags=re.IGNORECASE)

    content = replace_word_keep_case(content, src_character, new_character)

    if year and year != src_year:
        content = content.replace(f"{src_year} · Point", f"{year} · Point")
        content = content.replace(f'"datePublished": "{src_year}"', f'"datePublished": "{year}"')

    target = vault / "games" / game_id / "index.html"
    target.write_text(content, encoding="utf-8")
    ok(f"index.html generated: {target}")


def update_games_json(vault, game_id, title):
    games_json = vault / "_games.json"
    games = json.loads(games_json.read_text(encoding="utf-8"))
    # Check if already present
    for g in games:
        if g.get("id") == game_id:
            log(f"Game '{game_id}' already in _games.json - skipping")
            return
    games.append({
        "id": game_id,
        "title": title,
        "thumbnail": f"games/{game_id}/thumbnail.png",
        "status": "patched",
    })
    games_json.write_text(json.dumps(games, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok(f"_games.json updated ({len(games)} games)")


def update_sitemap(vault, game_id, title):
    sitemap = vault / "sitemap.xml"
    text = sitemap.read_text(encoding="utf-8")
    if f"/games/{game_id}/" in text:
        log(f"Game '{game_id}' already in sitemap.xml - skipping")
        return
    today = datetime.date.today().isoformat()
    entry = f"""
  <!-- {title} -->
  <url>
    <loc>https://seikios.com/games/{game_id}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
    <image:image>
      <image:loc>https://seikios.com/games/{game_id}/thumbnail.png</image:loc>
      <image:title>{title}</image:title>
      <image:caption>Play {title} free online &mdash; patched Flash game playable in your browser</image:caption>
    </image:image>
  </url>

"""
    # Insert before </urlset>
    if "</urlset>" not in text:
        fatal(f"Malformed sitemap.xml - no </urlset> tag")
    new_text = text.replace("</urlset>", entry + "</urlset>")
    sitemap.write_text(new_text, encoding="utf-8")
    ok(f"sitemap.xml updated with {game_id}")


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--swf", required=True, help="Path to input SWF file")
    parser.add_argument("--id", required=True, help="Game ID (kebab-case, e.g. homer-saw-game)")
    parser.add_argument("--title", required=True, help="Game title (e.g. 'Homer Simpson Saw Game')")
    parser.add_argument("--year", default="2010", help="Year published (default: 2010)")
    parser.add_argument("--thumbnail", help="Path to thumbnail PNG (optional but recommended)")
    parser.add_argument("--vault", default=str(VAULT_ROOT), help=f"Vault root (default: {VAULT_ROOT})")
    parser.add_argument("--jpexs", default=DEFAULT_JPEXS, help=f"JPEXS path (default: {DEFAULT_JPEXS})")
    parser.add_argument("--dry-run", action="store_true", help="Don't write any files")
    parser.add_argument("--skip-deploy", action="store_true", help="Stop after patching SWF, don't touch site files")
    parser.add_argument("--discover-only", action="store_true", help="Just print discovered names and exit")
    args = parser.parse_args()

    # Phase 1: Validate
    paths = validate_inputs(args)

    # Phase 2: Export scripts to a temp dir
    with tempfile.TemporaryDirectory(prefix=f"seikios_{args.id}_") as tmp:
        tmp_path = Path(tmp)
        scripts_dir = export_scripts(paths["jpexs"], paths["swf"], tmp_path / "export")

        # Phase 3: Discover names
        names = discover_names(scripts_dir)

        if args.discover_only:
            print("\n=== Discovered names ===")
            print(json.dumps(names, indent=2))
            return

        # Phase 4: Generate patch
        doaction = find_frame1_doaction(scripts_dir)
        orig_init = doaction.read_text(encoding="utf-8").strip()
        log(f"Original frame_1/DoAction content: {orig_init!r}")
        if not re.match(r"^xyz\d+\s*=\s*(true|false)\s*;\s*$", orig_init):
            warn(f"Unexpected original frame_1/DoAction. Expected `xyzN = true/false;`, got:\n{orig_init}")

        patched_as = generate_patch(paths["template"], names, orig_init)
        patched_as_file = tmp_path / "patched_DoAction.as"
        patched_as_file.write_text(patched_as, encoding="utf-8")
        ok(f"Patch generated: {patched_as_file} ({len(patched_as)} chars)")

        if args.dry_run:
            print("\n=== DRY RUN - would inject this into SWF ===")
            print(patched_as[:2000])
            print("...(truncated)")
            return

        # Phase 5: Inject
        patched_swf = tmp_path / f"{args.id}_patched.swf"
        inject_patch(paths["jpexs"], paths["swf"], patched_swf, patched_as_file)

        # Phase 6: Deploy (optional)
        if args.skip_deploy:
            # Copy patched SWF next to original for inspection
            keep = paths["swf"].parent / f"{args.id}_patched.swf"
            shutil.copy2(patched_swf, keep)
            ok(f"--skip-deploy: patched SWF kept at {keep}")
            return

        game_dir = deploy_swf(patched_swf, paths["vault"], args.id)
        deploy_thumbnail(paths["thumb"], game_dir)
        generate_index_html(paths["vault"], args.id, args.title, args.year)
        update_games_json(paths["vault"], args.id, args.title)
        update_sitemap(paths["vault"], args.id, args.title)

        ok(f"\n=== DONE ===")
        print(f"Test locally:  cd {paths['vault']} && python -m http.server 8000")
        print(f"Then visit:    http://localhost:8000/games/{args.id}/")
        print(f"\nRemember to run Phase 6 (manual play-test for broken transitions) before committing.")


if __name__ == "__main__":
    main()
