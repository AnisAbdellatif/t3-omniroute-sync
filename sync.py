#!/usr/bin/env python3
"""
t3-omniroute-sync — set up OmniRoute as a provider in T3 Code.

Just run:   python3 sync.py

The wizard will:
  1. ask for your OmniRoute address and API key
  2. fetch the models your OmniRoute actually serves (live catalog)
  3. let you tick the providers / models you want (arrow keys + space)
  4. create the ~/claude_omniroute folder and register an "Omniroute"
     Claude provider in T3 Code (with a backup of your T3 settings)

Only the Python 3.8+ standard library is used — nothing to install.
"""

from __future__ import annotations

import argparse
import datetime
import getpass
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:  # curses is missing on some Windows Pythons; we fall back to plain prompts
    import curses
except ImportError:  # pragma: no cover
    curses = None  # type: ignore

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

T3_SETTINGS_PATH = os.path.expanduser("~/.t3/userdata/settings.json")
OMNIROUTE_CLI_CONFIG = os.path.expanduser("~/.omniroute/config.json")
DEFAULT_HOME_PATH = "~/claude_omniroute"
__version__ = "0.3.1"
DEFAULT_PORT = 20128
INSTANCE_ID = "omniroute"
DISPLAY_NAME = "Omniroute"

EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]
EFFORT_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "Extra High", "max": "Max"}
PROVIDER_LABELS = {
    "antigravity": "Antigravity", "claude": "Anthropic", "openai": "OpenAI", "gemini": "Gemini",
    "github": "GitHub", "codex": "Codex", "openrouter": "OpenRouter", "deepseek": "DeepSeek",
}
PROVIDER_SHORT = {
    "antigravity": "AG", "claude": "A", "openai": "OAI", "gemini": "G",
    "github": "GH", "codex": "CX", "openrouter": "OR", "deepseek": "DS",
}
TAG_STYLES = ["prefix", "short-prefix", "suffix", "short-suffix", "none"]

# --------------------------------------------------------------------------- #
# Tiny UI helpers
# --------------------------------------------------------------------------- #

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t: str) -> str: return _c("1", t)
def dim(t: str) -> str: return _c("2", t)
def green(t: str) -> str: return _c("32", t)
def red(t: str) -> str: return _c("31", t)
def cyan(t: str) -> str: return _c("36", t)
def yellow(t: str) -> str: return _c("33", t)


class UserAbort(Exception):
    pass


def step(n: int, total: int, title: str) -> None:
    print(f"\n{cyan(f'Step {n}/{total}')} {bold(title)}")


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  {question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise UserAbort()
    return answer or default


def ask_secret(question: str) -> str:
    try:
        return getpass.getpass(f"  {question}: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise UserAbort()


def confirm(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = ask(f"{question} ({hint})").lower()
    return default if not answer else answer.startswith("y")


def mask(key: str) -> str:
    return key[:6] + "…" + key[-3:] if len(key) > 12 else "…" * bool(key)


# --------------------------------------------------------------------------- #
# Checklist widget (curses with plain-text fallback)
# --------------------------------------------------------------------------- #

Item = Tuple[str, str, str]  # (key, label, detail)


def checklist(title: str, subtitle: str, items: List[Item], selected: set) -> set:
    """Let the user tick items. Returns the set of selected keys."""
    if not items:
        return set()
    selected = set(selected)
    if curses and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            return curses.wrapper(_curses_checklist, title, subtitle, items, selected)
        except curses.error:
            pass  # terminal too small / unsupported -> plain mode
    return _text_checklist(title, subtitle, items, selected)


def _curses_checklist(stdscr, title, subtitle, items: List[Item], selected: set) -> set:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    cursor, top, query, filtering = 0, 0, "", False

    def visible() -> List[Item]:
        q = query.lower()
        return [it for it in items if q in it[1].lower() or q in it[0].lower()] if q else items

    while True:
        shown = visible()
        cursor = max(0, min(cursor, len(shown) - 1)) if shown else 0
        h, w = stdscr.getmaxyx()
        body_h = max(1, h - 6)
        if cursor < top:
            top = cursor
        if cursor >= top + body_h:
            top = cursor - body_h + 1

        stdscr.erase()
        stdscr.addnstr(0, 0, title, w - 1, curses.A_BOLD)
        stdscr.addnstr(1, 0, subtitle, w - 1, curses.A_DIM)
        flt = f"Filter: {query}{'_' if filtering else ''}" if (query or filtering) else "Press / to search"
        stdscr.addnstr(2, 0, f"{flt}    ({len(selected)} of {len(items)} selected)", w - 1)
        for row, it in enumerate(shown[top: top + body_h]):
            idx = top + row
            box = "[x]" if it[0] in selected else "[ ]"
            line = f" {box} {it[1]}"
            if it[2]:
                line += f"  — {it[2]}"
            attr = curses.A_REVERSE if idx == cursor else curses.A_NORMAL
            stdscr.addnstr(3 + row, 0, line, w - 1, attr)
        if not shown:
            stdscr.addnstr(3, 0, "  (nothing matches your filter)", w - 1, curses.A_DIM)
        stdscr.addnstr(h - 2, 0, "↑/↓ move   SPACE tick   a all   n none   / search   ENTER done   q cancel", w - 1, curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if filtering:
            if key in (10, 13, 27):
                filtering = False
                if key == 27:
                    query = ""
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                query = query[:-1]
            elif 32 <= key < 127:
                query += chr(key)
            cursor = top = 0
            continue
        if key in (curses.KEY_UP, ord("k")):
            cursor -= 1
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor += 1
        elif key == curses.KEY_PPAGE:
            cursor -= body_h
        elif key == curses.KEY_NPAGE:
            cursor += body_h
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = len(shown) - 1
        elif key == ord(" ") and shown:
            selected.symmetric_difference_update({shown[cursor][0]})
            cursor += 1
        elif key == ord("a"):
            selected.update(it[0] for it in shown)
        elif key == ord("n"):
            selected.difference_update(it[0] for it in shown)
        elif key == ord("/"):
            filtering = True
        elif key in (10, 13, curses.KEY_ENTER):
            return selected
        elif key in (ord("q"), 3):
            raise UserAbort()


def _text_checklist(title: str, subtitle: str, items: List[Item], selected: set) -> set:
    print(f"\n  {bold(title)}\n  {dim(subtitle)}")
    while True:
        for i, (key, label, detail) in enumerate(items, 1):
            box = green("[x]") if key in selected else "[ ]"
            print(f"  {i:>3}. {box} {label}" + (dim(f"  — {detail}") if detail else ""))
        reply = ask("Type numbers to toggle (e.g. 1 3 5-8), 'a' = all, 'n' = none, Enter = done").lower()
        if not reply:
            return selected
        if reply == "a":
            selected = {it[0] for it in items}
        elif reply == "n":
            selected = set()
        else:
            for tok in reply.replace(",", " ").split():
                m = re.fullmatch(r"(\d+)(?:-(\d+))?", tok)
                if not m:
                    print(red(f"  Didn't understand '{tok}'"))
                    continue
                lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
                for n in range(lo, hi + 1):
                    if 1 <= n <= len(items):
                        selected.symmetric_difference_update({items[n - 1][0]})


# --------------------------------------------------------------------------- #
# OmniRoute access
# --------------------------------------------------------------------------- #

class OmniRouteError(Exception):
    pass


def normalize_url(raw: str) -> str:
    """'100.1.2.3', 'localhost:20128', 'http://host:20128/v1/' -> 'http://host:20128'."""
    raw = raw.strip().rstrip("/")
    if not raw:
        raise OmniRouteError("The address is empty.")
    had_scheme = "://" in raw
    if not had_scheme:
        raw = "http://" + raw
    raw = re.sub(r"/(v1|api)(/.*)?$", "", raw)
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise OmniRouteError(f"'{raw}' doesn't look like an address.")
    host = parsed.hostname
    looks_local = host == "localhost" or re.fullmatch(r"[\d.]+", host) or ":" in host or "." not in host
    if not had_scheme and parsed.port is None and looks_local:
        raw += f":{DEFAULT_PORT}"
    return raw


def fetch_models(base_url: str, api_key: str, timeout: float = 15.0) -> List[str]:
    """Return the model ids OmniRoute serves (GET /v1/models)."""
    req = urllib.request.Request(
        base_url + "/v1/models",
        headers={"Authorization": f"Bearer {api_key}", "x-api-key": api_key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise OmniRouteError("OmniRoute rejected the API key (HTTP %d). Create/copy a key in the OmniRoute "
                                 "dashboard → API Keys, then try again." % e.code)
        raise OmniRouteError(f"OmniRoute answered with HTTP {e.code}. Is the address correct?")
    except urllib.error.URLError as e:
        raise OmniRouteError(f"Can't reach {base_url} ({e.reason}). Is OmniRoute running, and is the address right?")
    except (TimeoutError, OSError) as e:
        raise OmniRouteError(f"Connection to {base_url} failed: {e}")
    except ValueError:
        raise OmniRouteError(f"{base_url} didn't return JSON — it may not be an OmniRoute server.")

    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise OmniRouteError("Unexpected response from /v1/models.")
    ids = sorted({r["id"] if isinstance(r, dict) else str(r) for r in rows if (isinstance(r, dict) and r.get("id")) or isinstance(r, str)})
    if not ids:
        raise OmniRouteError("OmniRoute returned 0 models. Connect a provider in the OmniRoute dashboard first.")
    return ids


# --------------------------------------------------------------------------- #
# Model naming / grouping
# --------------------------------------------------------------------------- #

def provider_of(model_id: str) -> str:
    return model_id.split("/", 1)[0] if "/" in model_id else "other"


def provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider.replace("-", " ").replace("_", " ").title())


def pretty_name(model_id: str) -> str:
    """'antigravity/claude-sonnet-5-5' -> 'Claude Sonnet 5.5'."""
    raw = model_id.split("/", 1)[-1]
    date = re.search(r"-(\d{4})(\d{2})(\d{2})$", raw)
    date_str = ""
    if date:
        date_str = f" ({date.group(1)}-{date.group(2)}-{date.group(3)})"
        raw = raw[: date.start()]
    raw = re.sub(r"(?<=\D)-(\d+)-(\d+)(?=-|$)", r"-\1.\2", raw)
    words = [w if re.fullmatch(r"\d+(\.\d+)?", w) else w.capitalize() for w in raw.split("-")]
    return " ".join(words) + date_str


def provider_short(provider: str) -> str:
    if provider in PROVIDER_SHORT:
        return PROVIDER_SHORT[provider]
    caps = "".join(c for c in provider_label(provider) if c.isupper())
    return caps if len(caps) >= 2 else provider_label(provider)[:3].upper()


def tagged_name(model_id: str, tag_style: str) -> str:
    base, provider = pretty_name(model_id), provider_of(model_id)
    label, short = provider_label(provider), provider_short(provider)
    return {
        "prefix": f"[{label}] {base}", "short-prefix": f"[{short}] {base}",
        "suffix": f"{base} ({label})", "short-suffix": f"{base} ({short})", "none": base,
    }.get(tag_style, f"[{label}] {base}")


def split_effort(model_id: str) -> Tuple[str, Optional[str]]:
    for eff in EFFORT_ORDER:
        if model_id.endswith("-" + eff):
            return model_id[: -len(eff) - 1], eff
    return model_id, None


def build_entries(selected_ids: List[str], catalog: set, tag_style: str = "prefix", group: bool = True) -> List[Dict[str, Any]]:
    """
    Turn selected model ids into T3 customModels entries.

    Reasoning-effort variants (-low/-medium/-high/...) are folded into ONE entry with a
    "Reasoning" dropdown — but only when the un-suffixed base model really exists in the
    live catalog. Otherwise T3 would send a model name OmniRoute doesn't serve (the
    "not available in the active live catalog" error), so those variants stay separate.
    """
    entries: List[Dict[str, Any]] = []
    done: set = set()
    for mid in sorted(selected_ids):
        if mid in done:
            continue
        base, eff = split_effort(mid)
        if group and base in catalog:
            efforts = sorted(
                {split_effort(s)[1] for s in selected_ids if split_effort(s)[0] == base and split_effort(s)[1]},
                key=EFFORT_ORDER.index,
            )
            done.update(s for s in selected_ids if split_effort(s)[0] == base)
            entry: Dict[str, Any] = {"slug": base, "name": tagged_name(base, tag_style)}
            if efforts:
                default = "medium" if "medium" in efforts else efforts[0]
                entry["capabilities"] = {"optionDescriptors": [{
                    "id": "effort", "label": "Reasoning", "type": "select",
                    "options": [dict({"id": e, "label": EFFORT_LABELS[e]}, **({"isDefault": True} if e == default else {})) for e in efforts],
                }]}
            entries.append(entry)
        else:
            done.add(mid)
            entries.append({"slug": mid, "name": tagged_name(mid, tag_style)})
    return entries


# --------------------------------------------------------------------------- #
# T3 / Claude-home files
# --------------------------------------------------------------------------- #

def read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except ValueError as e:
        raise OmniRouteError(f"{path} isn't valid JSON ({e}). Fix or remove it, then run this again.")
    if not isinstance(data, dict):
        raise OmniRouteError(f"{path} has an unexpected format (expected a JSON object).")
    return data


def write_json_atomic(path: str, data: Dict[str, Any], mode: Optional[int] = None) -> None:
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if mode is not None:
            os.chmod(tmp, mode)
        else:
            shutil.copymode(path, tmp) if os.path.exists(path) else None
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def backup_file(path: str, keep: int = 10) -> Optional[str]:
    if not os.path.exists(path):
        return None
    dest = f"{path}.bak.{datetime.datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy2(path, dest)
    for old in sorted(glob.glob(path + ".bak.*"))[:-keep]:
        try:
            os.unlink(old)
        except OSError:
            pass
    return dest


def saved_connection(home_path: str) -> Tuple[str, str]:
    """(base_url, api_key) from a previous run, else best-effort defaults."""
    url = key = ""
    inst = read_json(T3_SETTINGS_PATH).get("providerInstances", {}).get(INSTANCE_ID, {})
    for env in inst.get("environment", []):
        if env.get("name") == "ANTHROPIC_BASE_URL":
            url = env.get("value", "")
    key = read_json(os.path.join(os.path.expanduser(home_path), "settings.json")).get("env", {}).get("ANTHROPIC_AUTH_TOKEN", "")
    if not url:
        cli = read_json(OMNIROUTE_CLI_CONFIG)
        url = cli.get("contexts", {}).get(cli.get("currentContext", ""), {}).get("baseUrl", "")
    key = key or os.environ.get("OMNIROUTE_API_KEY", "")
    return os.environ.get("OMNIROUTE_BASE_URL", url), key


def write_claude_home(home_path: str, base_url: str, api_key: str) -> str:
    """Create the Claude config dir and point its settings.json at OmniRoute."""
    home = os.path.expanduser(home_path)
    os.makedirs(home, mode=0o700, exist_ok=True)  # holds the API key
    path = os.path.join(home, "settings.json")
    settings = read_json(path)
    env = settings.setdefault("env", {})
    env["ANTHROPIC_BASE_URL"] = base_url
    env["ANTHROPIC_AUTH_TOKEN"] = api_key
    env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
    if os.path.exists(path):
        backup_file(path, keep=3)
    write_json_atomic(path, settings, mode=0o600)  # holds the API key
    return path


SHAREABLE_ASSETS = ["skills", "commands", "agents", "CLAUDE.md"]


def link_shared_assets(home_path: str, source_path: str = "~/.claude") -> List[str]:
    """Symlink shared skills, commands, agents, and CLAUDE.md from ~/.claude."""
    home = os.path.expanduser(home_path)
    source = os.path.expanduser(source_path)
    if os.path.abspath(home) == os.path.abspath(source):
        return []
    linked: List[str] = []
    for item in SHAREABLE_ASSETS:
        src = os.path.join(source, item)
        dst = os.path.join(home, item)
        if os.path.exists(src) and not os.path.lexists(dst):
            try:
                os.symlink(src, dst)
                linked.append(item)
            except OSError:
                pass
    return linked


def build_instance(existing: Dict[str, Any], base_url: str, home_path: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Update (or create) the T3 provider instance, preserving unrelated user settings."""
    wanted = {"ANTHROPIC_BASE_URL": base_url, "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"}
    env = [dict(e) for e in existing.get("environment", [])]
    for name, value in wanted.items():
        for e in env:
            if e.get("name") == name:
                e["value"] = value
                break
        else:
            env.append({"name": name, "value": value, "sensitive": False})
    config = dict(existing.get("config", {}))
    config.update({"homePath": home_path, "customModels": entries})
    config.setdefault("autoCompactWindow", "300000")
    inst = dict(existing)
    inst.update({"driver": "claudeAgent", "displayName": existing.get("displayName", DISPLAY_NAME),
                 "environment": env, "enabled": True, "config": config})
    return inst


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_status() -> int:
    inst = read_json(T3_SETTINGS_PATH).get("providerInstances", {}).get(INSTANCE_ID)
    if not inst:
        print("Omniroute provider: not set up yet. Run: python3 sync.py")
        return 0
    env = {e.get("name"): e.get("value") for e in inst.get("environment", [])}
    cfg = inst.get("config", {})
    models = cfg.get("customModels", [])
    print(f"Omniroute provider: {'enabled' if inst.get('enabled') else 'DISABLED'}")
    print(f"  Address:  {env.get('ANTHROPIC_BASE_URL', '(not set)')}")
    print(f"  Folder:   {cfg.get('homePath', '(default)')}")
    print(f"  Models:   {len(models)}")
    for m in models:
        slug = m.get("slug") if isinstance(m, dict) else m
        name = m.get("name", slug) if isinstance(m, dict) else m
        print(f"    • {name}  [{slug}]")
    return 0


def pick_connection(args: argparse.Namespace) -> Tuple[str, str, List[str]]:
    """Ask for address + key until OmniRoute accepts them. Returns (url, key, model_ids)."""
    saved_url, saved_key = saved_connection(args.home_path)
    url_default = args.url or saved_url or f"http://localhost:{DEFAULT_PORT}"
    key_default = args.key or saved_key
    interactive = not args.yes
    while True:
        try:
            if interactive:
                print(dim("  Example: 192.168.1.20:20128   or   http://localhost:20128"))
                typed = ask("OmniRoute address", url_default)
                url_default = typed  # remembered if we have to ask again
                url = normalize_url(typed)
                if key_default:
                    print(dim(f"  Press Enter to reuse the saved key ({mask(key_default)})."))
                else:
                    print(dim("  Your typing is hidden — paste the key and press Enter."))
                key = ask_secret("API key") or key_default
                if not key:
                    raise OmniRouteError("An API key is required.")
            else:
                url, key = normalize_url(url_default), key_default
                if not key:
                    raise OmniRouteError("--yes needs a key: pass --key or set OMNIROUTE_API_KEY.")
            print(f"  Connecting to {url} …")
            ids = fetch_models(url, key)
            print(green(f"  ✓ Connected — {len(ids)} models available."))
            return url, key, ids
        except OmniRouteError as e:
            print(red(f"  ✗ {e}"))
            if not interactive:
                raise
            if not confirm("Try again?", True):
                raise UserAbort()


def pick_models(ids: List[str], args: argparse.Namespace) -> List[str]:
    by_provider: Dict[str, List[str]] = {}
    for mid in ids:
        by_provider.setdefault(provider_of(mid), []).append(mid)

    is_claude = lambda m: "claude" in m.lower()
    try:
        pattern = re.compile(args.models, re.I) if args.models else None
    except re.error as e:
        raise OmniRouteError(f"--models isn't a valid regex: {e}")
    wanted_providers = {p.strip() for p in args.providers.split(",")} if args.providers else None

    # --- providers ---
    if wanted_providers is not None:
        chosen_providers = {p for p in by_provider if p in wanted_providers}
    elif args.yes or len(by_provider) == 1:
        chosen_providers = {p for p, ms in by_provider.items() if any(is_claude(m) for m in ms)} or set(by_provider)
    else:
        step(3, 5, "Choose providers")
        items = [(p, provider_label(p), f"{len(ms)} model{'s' * (len(ms) != 1)}" + (f", {sum(map(is_claude, ms))} Claude" if any(map(is_claude, ms)) else ""))
                 for p, ms in sorted(by_provider.items())]
        pre = {p for p, ms in by_provider.items() if any(is_claude(m) for m in ms)}
        chosen_providers = checklist("Which providers do you want in T3 Code?",
                                     "Providers that serve Claude models are pre-selected.", items, pre)
    candidates = [m for m in ids if provider_of(m) in chosen_providers]
    if not candidates:
        raise OmniRouteError("No models selected.")

    # --- models ---
    if args.yes or args.models or args.all:
        picked = [m for m in candidates if args.all or (pattern.search(m) if pattern else is_claude(m))]
        return picked
    step(4, 5, "Choose models")
    items: List[Item] = []
    for m in candidates:
        base, eff = split_effort(m)
        if base in ids and eff:
            continue  # folded into the base model's Reasoning dropdown
        variants = [split_effort(x)[1] for x in candidates if split_effort(x)[0] == m and split_effort(x)[1]]
        detail = ("Reasoning: " + "/".join(sorted(variants, key=EFFORT_ORDER.index))) if variants else ""
        items.append((m, f"{provider_label(provider_of(m))} · {pretty_name(m)}", detail))
    pre = {k for k, _, _ in items if is_claude(k)}
    keys = checklist("Which models do you want in T3 Code?",
                     "Claude models are pre-selected. Reasoning levels are folded into one model.", items, pre)
    picked = [m for m in candidates if (split_effort(m)[0] if split_effort(m)[0] in ids and split_effort(m)[1] else m) in keys]
    return picked


def pick_tag_style(sample_id: str) -> str:
    print(bold("\n  How should model names show their provider?"))
    for i, style in enumerate(TAG_STYLES, 1):
        print(f"    {i}) {tagged_name(sample_id, style)}")
    while True:
        reply = ask("Choose a number", "1")
        if reply.isdigit() and 1 <= int(reply) <= len(TAG_STYLES):
            return TAG_STYLES[int(reply) - 1]
        print(red("  Please type one of the numbers above."))


def cmd_setup(args: argparse.Namespace) -> int:
    print(bold("\n  OmniRoute → T3 Code setup"))
    print(dim("  This connects T3 Code to your OmniRoute so you can pick its models in the model menu.\n"))
    if not os.path.exists(T3_SETTINGS_PATH):
        print(red(f"  Couldn't find T3 Code's settings at {T3_SETTINGS_PATH}."))
        print("  Open T3 Code at least once, then run this again.")
        return 1

    step(1, 5, "Where is your OmniRoute?")
    url, key, ids = pick_connection(args)
    catalog = set(ids)

    if args.yes:
        step(2, 5, "Choosing models automatically")
    else:
        step(2, 5, "Where should the Claude config folder live?")
        args.home_path = ask("Folder", args.home_path)
    picked = pick_models(ids, args)
    if not picked:
        print(red("  No models selected — nothing to do."))
        return 1
    if args.source_tag is None:
        args.source_tag = "prefix" if args.yes else pick_tag_style(picked[0])
    entries = build_entries(picked, catalog, args.source_tag, group=not args.no_group)

    step(5, 5, "Review and apply")
    print(f"  Address : {url}")
    print(f"  API key : {mask(key)}")
    print(f"  Folder  : {args.home_path}" + (" (shares skills/commands from ~/.claude)" if not args.no_link else ""))
    print(f"  Models  : {len(entries)} entries ({len(picked)} variants)")
    for e in entries[:12]:
        efforts = [o["id"] for d in e.get("capabilities", {}).get("optionDescriptors", []) for o in d.get("options", [])]
        print(f"    • {e['name']}" + (dim(f"  (Reasoning: {'/'.join(efforts)})") if efforts else ""))
    if len(entries) > 12:
        print(dim(f"    … and {len(entries) - 12} more"))

    if args.dry_run:
        print(yellow("\n  Dry run — nothing was written."))
        return 0
    if not args.yes and not confirm("\n  Apply these settings?", True):
        raise UserAbort()

    settings = read_json(T3_SETTINGS_PATH)
    instances = settings.setdefault("providerInstances", {})
    existing = instances.get(INSTANCE_ID, {})
    home_file = write_claude_home(args.home_path, url, key)
    linked = [] if args.no_link else link_shared_assets(args.home_path)
    backup = backup_file(T3_SETTINGS_PATH)
    instances[INSTANCE_ID] = build_instance(existing, url, args.home_path, entries)
    write_json_atomic(T3_SETTINGS_PATH, settings)

    print(green("\n  ✓ All done!"))
    print(f"  • Claude folder ready : {os.path.expanduser(args.home_path)}")
    print(f"  • Credentials saved   : {home_file} (private, mode 600)")
    if linked:
        print(f"  • Shared assets linked: {', '.join(linked)} (from ~/.claude)")
    print(f"  • T3 provider         : '{DISPLAY_NAME}' with {len(entries)} models" + (" (updated)" if existing else " (created)"))
    if backup:
        print(dim(f"  • Backup of old T3 settings: {backup}"))
    print(bold("\n  Next: open T3 Code's model menu and pick an Omniroute model.") + dim(" (Restart T3 Code if it doesn't show up.)"))
    print(dim("  Re-run this script any time to add/remove models — your address and key are remembered.\n"))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Set up OmniRoute as a provider in T3 Code. Run with no options for the guided wizard.")
    p.add_argument("--url", help="OmniRoute address (skips the question's default)")
    p.add_argument("--key", help="OmniRoute API key (or set OMNIROUTE_API_KEY)")
    p.add_argument("--home-path", default=DEFAULT_HOME_PATH, help=f"Claude config folder (default {DEFAULT_HOME_PATH})")
    p.add_argument("--providers", help="Comma-separated provider ids to include, e.g. antigravity,claude")
    p.add_argument("--models", help="Regex of model ids to include (default: Claude models)")
    p.add_argument("--all", action="store_true", help="Include every model of the chosen providers")
    p.add_argument("--source-tag", choices=TAG_STYLES, default=None, help="How to label the provider in model names (default: prefix; the wizard asks)")
    p.add_argument("--no-group", action="store_true", help="Don't fold reasoning levels into one model")
    p.add_argument("--no-link", action="store_true", help="Don't symlink skills, commands, and agents from ~/.claude")
    p.add_argument("-y", "--yes", action="store_true", help="No questions: use flags/defaults")
    p.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--status", action="store_true", help="Show the current T3 Omniroute setup and exit")
    args = p.parse_args(argv)
    if os.environ.get("OMNIROUTE_API_KEY") and not args.key:
        args.key = os.environ["OMNIROUTE_API_KEY"]

    os.environ.setdefault("ESCDELAY", "25")
    try:
        return cmd_status() if args.status else cmd_setup(args)
    except (UserAbort, KeyboardInterrupt):
        print(yellow("\n  Cancelled — nothing was changed."))
        return 130
    except OmniRouteError as e:
        print(red(f"\n  ✗ {e}"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
