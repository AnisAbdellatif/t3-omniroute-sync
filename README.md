# t3-omniroute-sync 🚀

Bridge and synchronize AI models from **[OmniRoute](https://github.com/dvalov/omniroute)** into **T3 Code** as a dedicated provider instance.

---

## 💡 How It Works

1. **T3 Code Provider Architecture**:
   - T3 Code configures provider instances in `~/.t3/userdata/settings.json`.
   - By creating a `claudeAgent` driver instance pointed at OmniRoute's proxy endpoint (`ANTHROPIC_BASE_URL`), T3 Code launches Claude Code processes directly connected to OmniRoute.
   - Claude Code gateway discovery is enabled (`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`), allowing arbitrary model IDs.
   - Models in `customModels` can be rich objects with `capabilities.optionDescriptors`.

2. **Smart Reasoning / Thinking Level Grouping**:
   - Rather than creating 5-6 redundant entries in the UI for every model (`-low`, `-medium`, `-high`, `-xhigh`, `-max`), `t3-omniroute-sync` detects these suffixes and collapses them into **one base model** with an interactive **Reasoning (Effort)** selector dropdown directly in T3 Code!
   - For example, 68 raw Claude variants are cleanly grouped into **13 base models** with their exact supported reasoning levels.

---

## 📦 Installation

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

### 2. List grouped models discovered from OmniRoute
```bash
./sync.py --list
```

### 3. Sync Claude models with grouped reasoning (Default)
```bash
./sync.py --filter "^(anthropic|claude)/" --replace
```

### 4. Sync without grouping (flat list of all suffixes)
```bash
./sync.py --filter "^(anthropic|claude)/" --no-group-thinking
```

### 5. Preview changes with Dry Run (`--dry-run`)
```bash
./sync.py --dry-run
```

---

## 🛠️ CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--status` | Print current OmniRoute provider status in T3 Code | — |
| `--list` | Print discovered OmniRoute models without modifying settings | — |
| `--dry-run` | Preview configuration without touching disk | — |
| `--filter <regex>` | Filter model names with a regular expression | `"^(anthropic\|claude)/"` |
| `--all` | Include all discovered models (500+) | `False` |
| `--replace` | Overwrite `customModels` instead of merging with existing | `False` |
| `--no-group-thinking` | Keep each thinking level as a separate model entry | `False` (grouped by default) |
| `--base-url <url>` | Override OmniRoute API base URL | Auto-detected from `~/.omniroute/config.json` |
| `--home-path <dir>` | Claude Code home directory for OmniRoute | `~/.claude-omniroute` |

---

## 🔒 Safety & Backups

Every time settings are modified, an automatic timestamped backup is created:
```
~/.t3/userdata/settings.json.bak.<YYYYMMDD_HHMMSS>
```
