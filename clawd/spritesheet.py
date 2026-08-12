"""Pack each action's frames into a sprite sheet, plus a demo page.

    python3 spritesheet.py

Writes:
    sprites/<action>.png     one horizontal strip per action
    sprites/manifest.json    frame count / size / duration per action
    demo.html                self-contained page playing every action

Plain CPython with Pillow, no Blender.

Why sprite sheets
-----------------
354 loose PNGs and a set of GIFs are viewable but not usable. A strip plus
`background-position` steps is how these actually get consumed -- a status-line
pet, a web page, a game engine -- with one HTTP request per action and no
decoder involved.

The frames carry an opaque background, not alpha, and it is not one flat
colour -- there is a grey sky region (~213) above a cream floor (~240). So no
single page colour can hide the cell edges; sampling a corner and hoping was
tried and does not work. The page therefore presents each cell as a deliberate
rounded tile rather than pretending it is seamless.

Genuinely transparent sprites need a second render pass with
`film_transparent` and the floor hidden. Note the tradeoff: EEVEE has no
shadow catcher (that is Cycles-only), so alpha sprites lose the ground shadow
entirely rather than keeping it over transparency.
"""

import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEROOT = os.path.join(HERE, "out")
SPRITEDIR = os.path.join(HERE, "sprites")
CELL = int(os.environ.get("CLAWD_CELL", "160"))     # px per frame in the strip
FPS = 24.0

ACTIONS = ["idle", "walk", "jump", "wave", "look", "dance", "sleep",
           "turntable"]

os.makedirs(SPRITEDIR, exist_ok=True)

manifest = {"cell": CELL, "fps": FPS, "actions": {}}
page_bg = None

for action in ACTIONS:
    framedir = os.path.join(FRAMEROOT, action)
    if not os.path.isdir(framedir):
        print(f"  skip {action}: no frames at {framedir}")
        continue
    names = sorted(f for f in os.listdir(framedir) if f.endswith(".png"))
    if not names:
        print(f"  skip {action}: empty")
        continue

    frames = [Image.open(os.path.join(framedir, n)).convert("RGB")
              .resize((CELL, CELL), Image.LANCZOS) for n in names]

    if page_bg is None:                            # sample once, from a corner
        page_bg = "#%02x%02x%02x" % frames[0].getpixel((2, 2))

    sheet = Image.new("RGB", (CELL * len(frames), CELL))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * CELL, 0))

    path = os.path.join(SPRITEDIR, f"{action}.png")
    sheet.save(path, optimize=True)
    manifest["actions"][action] = {
        "frames": len(frames),
        "width": sheet.width,
        "duration_ms": int(round(1000.0 * len(frames) / FPS)),
    }
    print(f"  {action}: {len(frames)} frames, {sheet.width}x{CELL}, "
          f"{os.path.getsize(path) / 1024.0:.0f} KB")

manifest["page_bg"] = page_bg
with open(os.path.join(SPRITEDIR, "manifest.json"), "w") as fh:
    json.dump(manifest, fh, indent=2)

# --------------------------------------------------------------------------
# demo page: pure CSS steps() animation, no JS, no CDN, works from file://
# --------------------------------------------------------------------------
cards = []
rules = []
for action, meta in manifest["actions"].items():
    n = meta["frames"]
    secs = n / FPS
    rules.append(
        f"@keyframes play-{action} {{ from {{ background-position: 0 0; }} "
        f"to {{ background-position: -{meta['width']}px 0; }} }}\n"
        f".sprite.{action} {{ background-image: url('sprites/{action}.png'); "
        f"animation: play-{action} {secs:.3f}s steps({n}) infinite; }}")
    cards.append(
        f'<figure><div class="sprite {action}"></div>'
        f'<figcaption>{action} <span>{n}f</span></figcaption></figure>')

html = f"""<!DOCTYPE html>
<meta charset="utf-8">
<title>Clawd &mdash; action library</title>
<style>
  :root {{ --bg: #faf9f5; --ink: #141413; --accent: #d97757;
          --muted: #6b6862; --line: #e8e6dc; }}
  body {{ margin: 0; padding: 56px 40px; background: var(--bg);
         color: var(--ink);
         font: 15px/1.6 "Lora", Georgia, serif; }}
  h1 {{ font: 600 32px/1.2 "Poppins", Arial, sans-serif; margin: 0 0 8px; }}
  p.sub {{ margin: 0 0 40px; color: var(--muted); max-width: 60ch; }}
  .grid {{ display: grid; gap: 26px;
          grid-template-columns: repeat(auto-fill, minmax({CELL}px, 1fr));
          max-width: 1120px; }}
  figure {{ margin: 0; text-align: center; }}
  /* The sprite cells are opaque and not one flat colour, so they are framed
     as deliberate tiles rather than pretending to be seamless. */
  .sprite {{ width: {CELL}px; height: {CELL}px; margin: 0 auto;
            border-radius: 12px; overflow: hidden;
            box-shadow: 0 1px 2px rgba(20,20,19,.10),
                        0 6px 18px rgba(20,20,19,.07); }}
  figcaption {{ font: 600 12px/1 "Poppins", Arial, sans-serif;
               margin-top: 12px; letter-spacing: .06em;
               text-transform: uppercase; color: var(--accent); }}
  figcaption span {{ color: #9b978f; font-weight: 400; letter-spacing: 0; }}
  footer {{ margin-top: 52px; padding-top: 20px; border-top: 1px solid var(--line);
           color: var(--muted); font-size: 13px; max-width: 70ch; }}
  code {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px;
         background: var(--line); padding: 1px 5px; border-radius: 4px; }}
{chr(10).join('  ' + r.replace(chr(10), chr(10) + '  ') for r in rules)}
</style>
<h1>Clawd</h1>
<p class="sub">{len(manifest["actions"])} looping actions, rendered headless in
Blender and packed into CSS sprite strips. No JavaScript.</p>
<div class="grid">
{chr(10).join('  ' + c for c in cards)}
</div>
<footer>
  {CELL}px cells at {FPS:g}fps, driven by <code>steps()</code> on
  <code>background-position</code> &mdash; one image request per action, no
  decoder, no script. Cells are opaque: the renders contain both a sky and a
  floor region, so no single page colour hides their edges, and they are framed
  as tiles instead. Transparent sprites would need a second render pass with
  <code>film_transparent</code>, which in EEVEE also means losing the ground
  shadow &mdash; shadow catchers are Cycles-only.
</footer>
"""

with open(os.path.join(HERE, "demo.html"), "w") as fh:
    fh.write(html)

print(f"\ndemo.html written; page background sampled as {page_bg}")
