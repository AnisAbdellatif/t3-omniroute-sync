#!/usr/bin/env python3
"""
T3 Code ↔ OmniRoute Model & Provider Synchronizer
=================================================

Automates configuring OmniRoute as an active Claude-agent provider inside T3 Code
and syncs models discovered from OmniRoute into T3 Code's model picker.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
from typing import List, Set, Optional, Dict, Any

SETTINGS_PATH = os.path.expanduser("~/.t3/userdata/settings.json")
OMNIROUTE_CONFIG_PATH = os.path.expanduser("~/.omniroute/config.json")
CLAUDE_PROFILES_DIR = os.path.expanduser("~/.claude/profiles")
DEFAULT_BASE_URL = "http://100.66.176.99:20128"
DEFAULT_HOME_PATH = "~/.claude-omniroute"


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
    print(f"Custom Models: {len(custom_models)} loaded")
    if custom_models:
        print("\nLoaded Models:")
        for m in custom_models[:20]:
            print(f"  • {m}")
        if len(custom_models) > 20:
            print(f"  ... and {len(custom_models) - 20} more.")


def list_available_models(filter_pattern: Optional[str] = None):
    """List models discovered from OmniRoute Claude profiles."""
    models = discover_models_from_profiles(filter_pattern)
    print(f"=== Discovered {len(models)} OmniRoute Model(s) ===")
    for m in models:
        print(f"  • {m}")


def build_provider_config(base_url: str, home_path: str, custom_models: List[str]) -> Dict[str, Any]:
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
        description="Sync OmniRoute models into T3 Code settings as a custom Claude provider."
    )
    parser.add_argument("--status", action="store_true", help="Show current OmniRoute provider status in T3 Code")
    parser.add_argument("--list", action="store_true", help="List discovered OmniRoute models without modifying anything")
    parser.add_argument("--base-url", default=None, help=f"OmniRoute endpoint (default: auto-detected or {DEFAULT_BASE_URL})")
    parser.add_argument("--home-path", default=DEFAULT_HOME_PATH, help=f"Custom Claude home directory (default: {DEFAULT_HOME_PATH})")
    parser.add_argument("--filter", default=None, help="Regex pattern to filter models (e.g. 'antigravity', 'gemini|claude')")
    parser.add_argument("--all", action="store_true", help="Load ALL available models (500+ models)")
    parser.add_argument("--replace", action="store_true", help="Replace customModels entirely instead of merging")
    parser.add_argument("--dry-run", action="store_true", help="Preview configuration changes without writing to disk")

    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if args.list:
        list_available_models(args.filter)
        return 0

    base_url = args.base_url or get_omniroute_base_url()
    print(f"[*] OmniRoute Base URL: {base_url}")

    # Determine filter pattern
    pattern = args.filter
    if not args.all and not args.filter:
        print("[*] No filter specified. Defaulting to curated models (antigravity, claude, gemini, gpt).")
        print("    (Use --all to load all 500+ models, or --filter <pattern> to customize)")
        pattern = r"antigravity|claude|gemini|gpt"

    discovered_models = discover_models_from_profiles(pattern)
    print(f"[*] Discovered {len(discovered_models)} model(s) matching filter.")
    if not discovered_models:
        print("[-] No models found! Run 'omniroute setup-claude' first or check filter.", file=sys.stderr)
        return 1

    try:
        settings = load_t3_settings()
    except Exception as e:
        print(f"[-] Failed to load T3 settings: {e}", file=sys.stderr)
        return 1

    provider_instances = settings.setdefault("providerInstances", {})
    existing_instance = provider_instances.get("omniroute", {})
    existing_models = existing_instance.get("config", {}).get("customModels", [])

    if args.replace:
        final_models = discovered_models
    else:
        # Merge preserving order
        final_models = list(dict.fromkeys(existing_models + discovered_models))

    new_config = build_provider_config(base_url, args.home_path, final_models)

    if args.dry_run:
        print("\n--- [DRY RUN] Generated Configuration ---")
        print(json.dumps(new_config, indent=2))
        print(f"\nTotal models to be registered: {len(final_models)}")
        print("Sample models:")
        for m in final_models[:15]:
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
