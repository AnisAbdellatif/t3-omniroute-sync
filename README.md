# t3-omniroute-sync 🚀

Bridge and synchronize AI models from **[OmniRoute](https://github.com/dvalov/omniroute)** into **T3 Code** as a dedicated provider instance.

---

## 💡 How It Works

1. **T3 Code Provider Architecture**:
   - T3 Code configures provider instances in `~/.t3/userdata/settings.json`.
   - By creating a `claudeAgent` driver instance pointed at OmniRoute's proxy endpoint (`ANTHROPIC_BASE_URL`), T3 Code launches Claude Code processes directly connected to OmniRoute.
   - Claude Code gateway discovery is enabled (`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`), allowing arbitrary model IDs (like `antigravity/*`, `cxa/*`, `gemini-*`, etc.).
   - Any models placed in the provider's `customModels` array are directly registered and surfaced in T3 Code's model picker.

2. **OmniRoute Model Discovery**:
   - OmniRoute generates Claude profiles in `~/.claude/profiles/` (via `omniroute setup-claude`).
   - This tool discovers those models, applies your preferred filters, and injects them into T3 Code's settings.
   - Creates a timestamped backup of your settings before any change.

---

## 📦 Installation

Clone or open the repository:

```bash
cd ~/dev/t3-omniroute-sync
```

Optionally install as a global CLI command:
```bash
pip install -e .
```
Now you can run `t3-omniroute-sync` directly from any terminal.

---

## ⚡ Quick Start

### 1. Check current status in T3 Code
```bash
./sync.py --status
```

### 2. Preview changes with Dry Run (`--dry-run`)
```bash
./sync.py --dry-run
```

### 3. Sync Antigravity models only (recommended)
Loads all Gemini, Claude, and GPT models provided by Antigravity:
```bash
./sync.py --filter "^antigravity/"
```

### 4. Sync popular models (Antigravity, Claude, Gemini, GPT)
```bash
./sync.py --filter "antigravity|claude|gemini|gpt"
```

### 5. Sync ALL 500+ models from OmniRoute
```bash
./sync.py --all
```

### 6. Replace existing model list instead of merging
```bash
./sync.py --filter "^antigravity/" --replace
```

---

## 🛠️ CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--status` | Print current OmniRoute provider status in T3 Code | — |
| `--list` | Print discovered OmniRoute models without modifying settings | — |
| `--dry-run` | Preview configuration without touching disk | — |
| `--filter <regex>` | Filter model names with a regular expression | `"antigravity\|claude\|gemini\|gpt"` |
| `--all` | Include all discovered models (500+) | `False` |
| `--replace` | Overwrite `customModels` instead of merging with existing | `False` |
| `--base-url <url>` | Override OmniRoute API base URL | Auto-detected from `~/.omniroute/config.json` |
| `--home-path <dir>` | Claude Code home directory for OmniRoute | `~/.claude-omniroute` |

---

## 🔒 Safety & Backups

Every time settings are modified, a backup is created in:
```
~/.t3/userdata/settings.json.bak.<YYYYMMDD_HHMMSS>
```
You can restore anytime by copying the backup file back to `~/.t3/userdata/settings.json`.
