#!/usr/bin/env python3
"""Render the GitHub Pages site from profiles/, instances.yml, and artifacts/latest/.

Usage: python3 site/build.py [--out _site]

Requires PyYAML. Output is a fully static directory: index.html plus copies of
the source YAML and snapshot artifacts so every card can link to the raw file.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
REPO_URL = "https://github.com/Chicago-Offline/chioff-codeplugger-profiles-shared"
PAGE_URL = "https://chicago-offline.github.io/chioff-codeplugger-profiles-shared/"
CODEPLUGGER_URL = "https://chicago-offline.github.io/codeplugger/"

RADIO_NAMES = {
    "retevis_matetalk_p4": ("Retevis MateTalk P4", "UHF-only DMR/FM handheld, 400–470 MHz"),
    "baofeng_dm32": ("Baofeng DM-32", "Dual-band DMR/FM handheld with airband receive"),
    "baofeng_uv5r_mini": ("Baofeng UV-5R Mini", "Dual-band analog FM, programmed through CHIRP"),
    "ailunce_ha2": ("Ailunce HA2", "Dual-band analog FM, programmed through CHIRP"),
    "baofeng_bf888s": ("Baofeng BF-888S", "UHF-only analog FM, 16 fixed channels, programmed through CHIRP"),
}

TAPE_COLORS = {
    "blue": "#3b82f6",
    "yellow": "#eab308",
    "purple": "#a855f7",
    "red": "#ef4444",
    "green": "#22c55e",
    "orange": "#f97316",
    "black": "#111827",
    "white": "#e5e7eb",
}


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def radio_label(radio_id: str) -> str:
    return RADIO_NAMES.get(radio_id, (radio_id.replace("_", " ").title(), ""))[0]


def radio_blurb(radio_id: str) -> str:
    return RADIO_NAMES.get(radio_id, ("", ""))[1]


def leading_comment(text: str) -> list[str]:
    """Return the descriptive comment paragraphs that precede the first top-level key after the header."""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# yaml-language-server"):
            continue
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if body:
                current.append(body)
            elif current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if current:
            paragraphs.append(" ".join(current))
            current = []
        # Comments inside `zones:` describe individual zones, not the profile.
        if stripped.startswith("zones:"):
            break
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def load_profiles() -> list[dict]:
    profiles = []
    for path in sorted((ROOT / "profiles").rglob("*.yml")):
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        rel = path.relative_to(ROOT).as_posix()
        zones = data.get("zones") or []
        channel_count = sum(len(z.get("assignments") or []) for z in zones)
        profiles.append(
            {
                "id": data.get("id", path.stem),
                "name": data.get("name", path.stem),
                "radio": data.get("radio", path.parent.name),
                "extends": data.get("extends"),
                "description": leading_comment(text),
                "zones": zones,
                "channel_count": channel_count,
                "rel": rel,
            }
        )
    return profiles


def load_instances() -> dict[str, dict]:
    path = ROOT / "instances.yml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("instances") or {}


def load_snapshots() -> list[dict]:
    snapshots = []
    for manifest in sorted((ROOT / "artifacts" / "latest").rglob("manifest.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        folder = manifest.parent
        rel = folder.relative_to(ROOT).as_posix()
        snapshots.append(
            {
                "radio": data.get("radio", folder.parent.name),
                "instance": data.get("radio_instance", folder.name),
                "captured_at": data.get("captured_at"),
                "operation": data.get("operation"),
                "verification": data.get("verification"),
                "reference_profile": data.get("reference_profile"),
                "generator_commit": data.get("reference_generator_commit"),
                "rel": rel,
                "has_reference": (folder / "reference.html").exists(),
                "has_toml": (folder / "current.toml").exists(),
            }
        )
    return snapshots


def fmt_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return esc(value)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def assignment_chip(item: object) -> str:
    if isinstance(item, dict):
        aid = item.get("id", "")
        alias = item.get("display_name")
        inner = esc(aid)
        if alias:
            inner += f' <span class="alias">→ {esc(alias)}</span>'
        return f'<span class="chip" title="{esc(json.dumps(item))}">{inner}</span>'
    return f'<span class="chip">{esc(item)}</span>'


def render_profile(p: dict, snapshot_profiles: set[str]) -> str:
    zone_count = len(p["zones"])
    badges = [
        f'<span class="badge">{esc(radio_label(p["radio"]))}</span>',
        f'<span class="badge">{zone_count} zone{"s" if zone_count != 1 else ""}</span>',
        f'<span class="badge">{p["channel_count"]} channel{"s" if p["channel_count"] != 1 else ""}</span>',
    ]
    if p["extends"]:
        badges.append(f'<span class="badge warn">extends {esc(p["extends"])}</span>')
    if p["id"] in snapshot_profiles:
        badges.append('<span class="badge ok">On a radio</span>')

    desc = "".join(f"<p>{esc(par)}</p>" for par in p["description"])
    zones_html = []
    for z in p["zones"]:
        assignments = z.get("assignments") or []
        zones_html.append(
            '<div class="zone">'
            f'<div class="zone-head"><strong>{esc(z.get("name", z.get("id")))}</strong>'
            f'<span>{esc(z.get("id"))} · {len(assignments)}</span></div>'
            f'<div class="chips">{"".join(assignment_chip(a) for a in assignments)}</div>'
            "</div>"
        )

    return (
        f'<article class="profile" id="profile-{esc(p["id"])}">'
        f'<header><h4>{esc(p["name"])}</h4><span class="pid">{esc(p["id"])}</span></header>'
        f'<div class="badges">{"".join(badges)}</div>'
        + (f'<div class="desc">{desc}</div>' if desc else "")
        + "".join(zones_html)
        + '<div class="links">'
        f'<a href="{esc(p["rel"])}">Raw YAML</a>'
        f'<a href="{REPO_URL}/blob/main/{esc(p["rel"])}" target="_blank" rel="noopener">View on GitHub ↗</a>'
        "</div>"
        "</article>"
    )


def render_profiles(profiles: list[dict], snapshot_profiles: set[str]) -> str:
    by_radio: dict[str, list[dict]] = {}
    for p in profiles:
        by_radio.setdefault(p["radio"], []).append(p)
    groups = []
    for radio_id in sorted(by_radio, key=radio_label):
        cards = "".join(render_profile(p, snapshot_profiles) for p in by_radio[radio_id])
        blurb = radio_blurb(radio_id)
        groups.append(
            f'<div class="radio-group" id="radio-{esc(radio_id)}">'
            f"<h3>{esc(radio_label(radio_id))}</h3>"
            + (f"<p>{esc(blurb)} · <code>{esc(radio_id)}</code></p>" if blurb else f"<p><code>{esc(radio_id)}</code></p>")
            + f'<div class="profiles">{cards}</div></div>'
        )
    return "".join(groups) or '<div class="empty">No profiles checked in yet.</div>'


def render_fleet(instances: dict[str, dict], profile_ids: set[str], snapshots: list[dict]) -> str:
    if not instances:
        return '<div class="empty">No radios registered in <code>instances.yml</code>.</div>'
    snap_by_instance = {s["instance"]: s for s in snapshots}
    rows = []
    for key, inst in instances.items():
        profile = inst.get("profile") or ""
        profile_cell = (
            f'<a href="#profile-{esc(profile)}" class="mono">{esc(profile)}</a>'
            if profile in profile_ids
            else f'<span class="mono muted">{esc(profile)}</span>'
        )
        tape = inst.get("tape_color")
        color = TAPE_COLORS.get(str(tape).lower(), "#6b7280") if tape else None
        tape_cell = f'<span class="dot" style="background:{color}"></span>{esc(tape)}' if tape else '<span class="muted">—</span>'
        snap = snap_by_instance.get(key)
        snap_cell = (
            f'<a href="{esc(snap["rel"])}/reference.html">Reference</a>'
            if snap and snap["has_reference"]
            else '<span class="muted">—</span>'
        )
        dmr_id = inst.get("dmr_id")
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(inst.get("label", key))}</td>'
            f"<td>{esc(radio_label(inst.get('radio', '')))}</td>"
            f"<td>{profile_cell}</td>"
            f'<td class="num">{esc(dmr_id) if dmr_id is not None else "<span class=muted>—</span>"}</td>'
            f'<td class="mono">{esc(inst.get("dmr_contact_name") or "")}</td>'
            f"<td>{tape_cell}</td>"
            f"<td>{esc(inst.get('assigned_to') or '')}</td>"
            f"<td>{snap_cell}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>Radio</th><th>Model</th><th>Profile</th><th>DMR ID</th><th>Contact</th><th>Tape</th><th>Assigned</th><th>Snapshot</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_snapshots(snapshots: list[dict], instances: dict[str, dict], profile_ids: set[str]) -> str:
    if not snapshots:
        return '<div class="empty">No verified radio snapshots under <code>artifacts/latest/</code> yet.</div>'
    rows = []
    for s in snapshots:
        label = instances.get(s["instance"], {}).get("label", s["instance"])
        prof = s["reference_profile"] or ""
        prof_cell = (
            f'<a href="#profile-{esc(prof)}" class="mono">{esc(prof)}</a>'
            if prof in profile_ids
            else f'<span class="mono muted">{esc(prof) or "—"}</span>'
        )
        links = []
        if s["has_reference"]:
            links.append(f'<a href="{esc(s["rel"])}/reference.html">Reference</a>')
        if s["has_toml"]:
            links.append(f'<a href="{esc(s["rel"])}/current.toml">current.toml</a>')
        links.append(f'<a href="{esc(s["rel"])}/manifest.json">Manifest</a>')
        verification = s["verification"] or ""
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(label)}</td>'
            f"<td>{esc(radio_label(s['radio']))}</td>"
            f"<td>{prof_cell}</td>"
            f'<td class="num">{fmt_time(s["captured_at"])}</td>'
            f'<td><span class="mono">{esc(s["operation"] or "")}</span>'
            + (f'<br><span class="muted">{esc(verification)}</span>' if verification else "")
            + "</td>"
            f"<td>{' · '.join(links)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>Radio</th><th>Model</th><th>Profile</th><th>Captured</th><th>Operation</th><th>Files</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_page(profiles: list[dict], instances: dict[str, dict], snapshots: list[dict]) -> str:
    profile_ids = {p["id"] for p in profiles}
    snapshot_profiles = {s["reference_profile"] for s in snapshots if s["reference_profile"]}
    radios = sorted({p["radio"] for p in profiles}, key=radio_label)
    radio_list = ", ".join(radio_label(r) for r in radios) or "supported radios"
    total_channels = sum(p["channel_count"] for p in profiles)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    description = (
        "Ready-made codeplugger profiles for the Chicago Offline community net: "
        f"{len(profiles)} profiles across {radio_list}, plus the registry of shared radios and their last verified state."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{PAGE_URL}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="ChiOff shared profiles — the community net, ready for your radio" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{PAGE_URL}" />
  <meta property="og:image" content="{PAGE_URL}logo.svg" />
  <meta name="twitter:card" content="summary" />
  <title>ChiOff shared profiles — Chicago Offline codeplugs</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg" />
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <header>
    <div class="wrap">
      <a class="brand" href="#top"><img src="logo.svg" alt="" /> ChiOff shared profiles</a>
      <nav>
        <a href="#profiles">Profiles</a>
        <a href="#fleet">Fleet</a>
        <a href="#snapshots">Snapshots</a>
        <a href="#start">Use them</a>
      </nav>
      <a class="repo-link" href="{REPO_URL}" target="_blank" rel="noopener">GitHub ↗</a>
    </div>
  </header>

  <main id="top">
    <div class="hero">
      <div class="wrap">
        <div>
          <p class="eyebrow">Chicago Offline · shared codeplug profiles</p>
          <h1>The community net, ready for your radio.</h1>
          <p class="lead">
            Version-controlled <a href="{CODEPLUGGER_URL}" target="_blank" rel="noopener">codeplugger</a>
            profiles that put the Chicago Offline GMRS, MURS, and DMR channels into each supported
            radio the same way every time. Browse what each profile loads, which radios carry it,
            and the last verified state of every shared handset.
          </p>
          <div class="actions">
            <a class="button primary" href="#profiles">Browse profiles</a>
            <a class="button" href="{REPO_URL}" target="_blank" rel="noopener">View on GitHub</a>
            <a class="button" href="{CODEPLUGGER_URL}" target="_blank" rel="noopener">About codeplugger</a>
          </div>
        </div>
        <img src="logo.svg" alt="codeplugger logo: a handheld radio with a code glyph on its screen and plug prongs at its base" />
      </div>
    </div>

    <section id="profiles">
      <div class="wrap">
        <h2>Profiles</h2>
        <p class="sub">
          {len(profiles)} profile{"s" if len(profiles) != 1 else ""} · {total_channels} channel assignments · grouped by radio.
          Each zone lists its SSRF assignment IDs in radio order; a <span class="chip">id <span class="alias">→ name</span></span>
          chip means the profile overrides the display name to fit the radio.
        </p>
        {render_profiles(profiles, snapshot_profiles)}
      </div>
    </section>

    <section id="fleet">
      <div class="wrap">
        <h2>Shared fleet</h2>
        <p class="sub">
          Physical radios registered in <code>instances.yml</code> against a shared profile.
          Operators' personal codeplugs live in their own private profile repos and are not listed here.
        </p>
        {render_fleet(instances, profile_ids, snapshots)}
      </div>
    </section>

    <section id="snapshots">
      <div class="wrap">
        <h2>Verified snapshots</h2>
        <p class="sub">
          The last read-back-verified state of each shared radio, from <code>artifacts/latest/</code>.
          This is a device-state record, not a generated source, so it can lag the current profile.
        </p>
        {render_snapshots(snapshots, instances, profile_ids)}
      </div>
    </section>

    <section id="start">
      <div class="wrap">
        <h2>Use these profiles</h2>
        <p class="sub">Clone this repo next to <code>codeplugger</code>, <code>ssrf-lite</code>, and <code>chioff-ssrf-shared</code>, then build from the codeplugger checkout.</p>
        <div class="start">
          <div>
            <h3>Validate a shared profile</h3>
<pre><code>uv run codeplugger-profile \\
  ../chioff-codeplugger-profiles-shared/profiles/baofeng_dm32/chioff_shared.yml \\
  --ssrf-root ../ssrf-lite/ssrf \\
  --ssrf-root ../chioff-ssrf-shared/ssrf</code></pre>
          </div>
          <div>
            <h3>Export for your radio</h3>
<pre><code><span class="c"># DM-32: qdmr YAML, then dmrconf write</span>
uv run codeplugger-profile \\
  ../chioff-codeplugger-profiles-shared/profiles/baofeng_dm32/chioff_shared.yml \\
  --ssrf-root ../ssrf-lite/ssrf \\
  --ssrf-root ../chioff-ssrf-shared/ssrf \\
  --output-format qdmr-yaml &gt; codeplug.yaml</code></pre>
          </div>
          <div>
            <h3>Check the shared fleet</h3>
<pre><code>uv run codeplugger-fleet \\
  --instance-registry ../chioff-codeplugger-profiles-shared/instances.yml \\
  --profiles-root ../chioff-codeplugger-profiles-shared/profiles \\
  --ssrf-root ../ssrf-lite/ssrf \\
  --ssrf-root ../chioff-ssrf-shared/ssrf</code></pre>
          </div>
          <div>
            <h3>Derive your own variant</h3>
<pre><code>version: "0.1"
id: "my_dm32"
name: "My DM-32"
radio: "baofeng_dm32"
extends: "chioff_dm32_shared"
zones:
  - id: "mine"
    name: "Mine"
    assignments:
      - "asg_my_local_repeater"</code></pre>
          </div>
        </div>
        <p class="generated">Generated {generated} from <code>profiles/</code>, <code>instances.yml</code>, and <code>artifacts/latest/</code> at the latest commit on <code>main</code>.</p>
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">
      <span>© 2026 Eric Muehlstein · a <a href="https://chicagooffline.com">Chicago Offline</a> project</span>
      <span><a href="{REPO_URL}">Source</a> · <a href="{CODEPLUGGER_URL}">codeplugger</a> · <a href="{REPO_URL}/issues">Issues</a></span>
    </div>
  </footer>
</body>
</html>
"""


def copy_tree(src: Path, dst: Path, patterns: tuple[str, ...]) -> None:
    if not src.exists():
        return
    for path in src.rglob("*"):
        if path.is_file() and any(path.match(p) for p in patterns):
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "_site"), help="output directory (default: _site)")
    args = parser.parse_args()
    out = Path(args.out).resolve()

    profiles = load_profiles()
    instances = load_instances()
    snapshots = load_snapshots()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    (out / "index.html").write_text(render_page(profiles, instances, snapshots), encoding="utf-8")
    for asset in ("style.css", "logo.svg", "favicon.svg"):
        shutil.copy2(SITE / asset, out / asset)
    copy_tree(ROOT / "profiles", out / "profiles", ("*.yml", "*.yaml"))
    copy_tree(ROOT / "artifacts" / "latest", out / "artifacts" / "latest", ("*.html", "*.toml", "*.json"))
    if (ROOT / "instances.yml").exists():
        shutil.copy2(ROOT / "instances.yml", out / "instances.yml")
    (out / ".nojekyll").touch()

    print(f"built {out}: {len(profiles)} profiles, {len(instances)} instances, {len(snapshots)} snapshots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
