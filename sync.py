#!/usr/bin/env python3
"""
T3 Code ↔ OmniRoute Model & Provider Synchronizer
=================================================

Automates configuring OmniRoute as an active Claude-agent provider inside T3 Code
and syncs models discovered from OmniRoute into T3 Code's model picker.

Supports grouping thinking / reasoning effort levels (low, medium, high, xhigh, max)
into an interactive dropdown under each base model rather than displaying them as separate models.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
from typing import List, Set, Optional, Dict, Any, Union

SETTINGS_PATH = os.path.expanduser("~/.t3/userdata/settings.json")
OMNIROUTE_CONFIG_PATH = os.path.expanduser("~/.omniroute/config.json")
CLAUDE_PROFILES_DIR = os.path.expanduser("~/.claude/profiles")
DEFAULT_BASE_URL = "http://100.66.176.99:20128"
DEFAULT_HOME_PATH = "~/.claude-omniroute"

EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]
EFFORT_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra High",
    "max": "Max"
}


def get_omniroute_base_url() -> str:
    """Detect OmniRoute base URL from ~/.omniroute/config.json if available."""
    if os.path.exists(OMNIROUTE_CONFIG_PATH):
        try:
            with open(OMNIROUTE_CONFIG_PATH) as f:
                data = json.load(f)
                current_context = data.get("currentContext", "default")
                contexts = data.get("contexts", {})
                if current_context in contexts:
                    base_url = contexts[current_context].get("baseUrl")
                    if base_url:
                        return base_url
        except Exception as e:
            print(f"[!] Warning reading {OMNIROUTE_CONFIG_PATH}: {e}", file=sys.stderr)
    return DEFAULT_BASE_URL


def discover_models_from_profiles(pattern_filter: Optional[str] = None) -> List[str]:
    """Extract model IDs from ~/.claude/profiles/*/settings.json."""
    if not os.path.exists(CLAUDE_PROFILES_DIR):
        return []

    profile_files = glob.glob(os.path.join(CLAUDE_PROFILES_DIR, "*/settings.json"))
    models: Set[str] = set()
    for pf in profile_files:
        try:
            with open(pf) as f:
                data = json.load(f)
                m = data.get("model") or data.get("env", {}).get("ANTHROPIC_MODEL")
                if m:
                    if pattern_filter:
                        if re.search(pattern_filter, m, re.IGNORECASE):
                            models.add(m)
                    else:
                        models.add(m)
        except Exception:
            continue
    return sorted(list(models))


def format_model_name(slug: str) -> str:
    """Generate a clean human-readable name for a model slug."""
    raw = slug.split("/", 1)[-1]
    date_match = re.search(r"-(\d{4})(\d{2})(\d{2})", raw)
    date_str = ""
    if date_match:
        date_str = f" ({date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)})"
        raw = raw[:date_match.start()]
    # Convert version numbers like -5-5 to -5.5
    raw = re.sub(r"-(\d+)-(\d+)", r"-\1.\2", raw)
    parts = raw.split("-")
    cleaned = [p.capitalize() if not re.match(r"^\d+(\.\d+)?$", p) else p for p in parts]
    return " ".join(cleaned) + date_str


def group_models_by_thinking(model_slugs: List[str]) -> List[Dict[str, Any]]:
    """
    Groups models with reasoning effort suffixes (-low, -medium, -high, -xhigh, -max)
    into a single CustomModelEntry with optionDescriptors for effort.
    """
    groups: Dict[str, Set[str]] = {}
    for m in model_slugs:
        matched_effort = None
        for eff in EFFORT_ORDER:
            suffix = f"-{eff}"
            if m.endswith(suffix):
                matched_effort = eff
                base_slug = m[:-len(suffix)]
                break
        if not matched_effort:
            base_slug = m
        groups.setdefault(base_slug, set())
        if matched_effort:
            groups[base_slug].add(matched_effort)

    entries = []
    for base_slug, efforts in sorted(groups.items()):
        name = format_model_name(base_slug)
        if efforts:
            supported_efforts = [e for e in EFFORT_ORDER if e in efforts]
            default_effort = "medium" if "medium" in supported_efforts else supported_efforts[0]
            options = []
            for e in supported_efforts:
                opt = {"id": e, "label": EFFORT_LABELS[e]}
                if e == default_effort:
                    opt["isDefault"] = True
                options.append(opt)

            entry = {
                "slug": base_slug,
                "name": name,
                "capabilities": {
                    "optionDescriptors": [
                        {
                            "id": "effort",
                            "label": "Reasoning",
                            "type": "select",
                            "options": options
                        }
                    ]
                }
            }
        else:
            entry = {
                "slug": base_slug,
                "name": name
            }
        entries.append(entry)
    return entries


def load_t3_settings() -> Dict[str, Any]:
    """Load ~/.t3/userdata/settings.json."""
    if not os.path.exists(SETTINGS_PATH):
        raise FileNotFoundError(f"T3 settings file not found at: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_t3_settings(settings: Dict[str, Any], backup: bool = True) -> Optional[str]:
    """Safely save settings to ~/.t3/userdata/settings.json with timestamped backup."""
    backup_path = None
    if backup and os.path.exists(SETTINGS_PATH):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{SETTINGS_PATH}.bak.{timestamp}"
        shutil.copy2(SETTINGS_PATH, backup_path)

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    return backup_path


def show_status():
    """Print current OmniRoute provider status in T3 Code."""
    print("=== T3 Code OmniRoute Provider Status ===")
    try:
        settings = load_t3_settings()
    except Exception as e:
        print(f"Error loading T3 settings: {e}")
        return

    instances = settings.get("providerInstances", {})
    omniroute = instances.get("omniroute")
    if not omniroute:
        print("OmniRoute provider: [NOT CONFIGURED]")
        return

    enabled = omniroute.get("enabled", False)
    driver = omniroute.get("driver", "unknown")
    cfg = omniroute.get("config", {})
    custom_models = cfg.get("customModels", [])
    home_path = cfg.get("homePath", "default")

    env_map = {item.get("name"): item.get("value") for item in omniroute.get("environment", [])}
    base_url = env_map.get("ANTHROPIC_BASE_URL", "not set")

    print(f"Provider:      Omniroute")
    print(f"Enabled:       {'YES' if enabled else 'NO'}")
    print(f"Driver:        {driver}")
    print(f"Base URL:      {base_url}")
    print(f"Home Path:     {home_path}")
    print(f"Custom Models: {len(custom_models)} registered")
    if custom_models:
        print("\nRegistered Models:")
        for item in custom_models[:20]:
            if isinstance(item, dict):
                slug = item.get("slug", "unknown")
                name = item.get("name", slug)
                opts = item.get("capabilities", {}).get("optionDescriptors", [])
                effort_opt = next((o for o in opts if o.get("id") == "effort"), None)
                if effort_opt:
                    efforts = [c.get("id") for c in effort_opt.get("options", [])]
                    print(f"  • {name} ({slug}) [Reasoning: {', '.join(efforts)}]")
                else:
                    print(f"  • {name} ({slug})")
            else:
                print(f"  • {item}")
        if len(custom_models) > 20:
            print(f"  ... and {len(custom_models) - 20} more.")


def list_available_models(filter_pattern: Optional[str] = None, group_thinking: bool = True):
    """List models discovered from OmniRoute Claude profiles."""
    raw_models = discover_models_from_profiles(filter_pattern)
    if group_thinking:
        grouped = group_models_by_thinking(raw_models)
        print(f"=== Discovered {len(grouped)} Grouped OmniRoute Model(s) (from {len(raw_models)} raw profiles) ===")
        for item in grouped:
            slug = item["slug"]
            name = item["name"]
            opts = item.get("capabilities", {}).get("optionDescriptors", [])
            effort_opt = next((o for o in opts if o.get("id") == "effort"), None)
            if effort_opt:
                efforts = [c.get("id") for c in effort_opt.get("options", [])]
                print(f"  • {name} ({slug}) [Reasoning: {', '.join(efforts)}]")
            else:
                print(f"  • {name} ({slug})")
    else:
        print(f"=== Discovered {len(raw_models)} Raw OmniRoute Model(s) ===")
        for m in raw_models:
            print(f"  • {m}")


def build_provider_config(base_url: str, home_path: str, custom_models: List[Any]) -> Dict[str, Any]:
    """Construct providerInstance JSON structure for OmniRoute."""
    return {
        "driver": "claudeAgent",
        "displayName": "Omniroute",
        "environment": [
            {
                "name": "ANTHROPIC_BASE_URL",
                "value": base_url,
                "sensitive": False
            },
            {
                "name": "ANTHROPIC_AUTH_TOKEN",
                "value": "",
                "sensitive": True,
                "valueRedacted": True
            },
            {
                "name": "ANTHROPIC_API_KEY",
                "value": "",
                "sensitive": False
            },
            {
                "name": "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
                "value": "1",
                "sensitive": False
            }
        ],
        "enabled": True,
        "config": {
            "homePath": home_path,
            "autoCompactWindow": "300000",
            "customModels": custom_models
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sync OmniRoute models into T3 Code settings with optional thinking level grouping."
    )
    parser.add_argument("--status", action="store_true", help="Show current OmniRoute provider status in T3 Code")
    parser.add_argument("--list", action="store_true", help="List discovered OmniRoute models without modifying anything")
    parser.add_argument("--base-url", default=None, help=f"OmniRoute endpoint (default: auto-detected or {DEFAULT_BASE_URL})")
    parser.add_argument("--home-path", default=DEFAULT_HOME_PATH, help=f"Custom Claude home directory (default: {DEFAULT_HOME_PATH})")
    parser.add_argument("--filter", default=None, help="Regex pattern to filter models (e.g. '^(anthropic|claude)/')")
    parser.add_argument("--all", action="store_true", help="Load ALL available models (500+ models)")
    parser.add_argument("--replace", action="store_true", help="Replace customModels entirely instead of merging")
    parser.add_argument("--no-group-thinking", action="store_true", help="Do not group thinking levels; list each variant as separate model")
    parser.add_argument("--dry-run", action="store_true", help="Preview configuration changes without writing to disk")

    args = parser.parse_args()
    group_thinking = not args.no_group_thinking

    if args.status:
        show_status()
        return 0

    if args.list:
        list_available_models(args.filter, group_thinking=group_thinking)
        return 0

    base_url = args.base_url or get_omniroute_base_url()
    print(f"[*] OmniRoute Base URL: {base_url}")

    # Determine filter pattern
    pattern = args.filter
    if not args.all and not args.filter:
        print("[*] No filter specified. Defaulting to '^(anthropic|claude)/'.")
        pattern = r"^(anthropic|claude)/"

    discovered_slugs = discover_models_from_profiles(pattern)
    print(f"[*] Discovered {len(discovered_slugs)} raw model profile(s) matching filter.")
    if not discovered_slugs:
        print("[-] No models found! Run 'omniroute setup-claude' first or check filter.", file=sys.stderr)
        return 1

    if group_thinking:
        models_to_register = group_models_by_thinking(discovered_slugs)
        print(f"[*] Grouped into {len(models_to_register)} base model(s) with interactive Reasoning selectors.")
    else:
        models_to_register = discovered_slugs
        print(f"[*] Registering {len(models_to_register)} flat model slug(s).")

    try:
        settings = load_t3_settings()
    except Exception as e:
        print(f"[-] Failed to load T3 settings: {e}", file=sys.stderr)
        return 1

    provider_instances = settings.setdefault("providerInstances", {})
    existing_instance = provider_instances.get("omniroute", {})
    existing_models = existing_instance.get("config", {}).get("customModels", [])

    if args.replace:
        final_models = models_to_register
    else:
        # Merge preserving order by slug
        seen_slugs = set()
        final_models = []
        for item in existing_models:
            slug = item.get("slug") if isinstance(item, dict) else item
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                final_models.append(item)
        for item in models_to_register:
            slug = item.get("slug") if isinstance(item, dict) else item
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                final_models.append(item)

    new_config = build_provider_config(base_url, args.home_path, final_models)

    if args.dry_run:
        print("\n--- [DRY RUN] Generated Configuration ---")
        print(json.dumps(new_config, indent=2)[:1500])
        print(f"\nTotal models to be registered: {len(final_models)}")
        print("Sample models:")
        for m in final_models[:15]:
            if isinstance(m, dict):
                print(f"  • {m.get('name')} ({m.get('slug')})")
            else:
                print(f"  • {m}")
        if len(final_models) > 15:
            print(f"  ... and {len(final_models) - 15} more.")
        return 0

    provider_instances["omniroute"] = new_config

    try:
        backup_file = save_t3_settings(settings, backup=True)
        if backup_file:
            print(f"[+] Backup created: {backup_file}")
        print(f"[+] Updated {SETTINGS_PATH}")
        print(f"[+] OmniRoute provider successfully configured with {len(final_models)} model(s).")
        print("[*] Open or re-open the model picker in T3 Code to view your models!")
    except Exception as e:
        print(f"[-] Failed to save T3 settings: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
