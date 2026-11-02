# t3-omniroute-sync 🚀

Bridge and synchronize AI models from **[OmniRoute](https://github.com/dvalov/omniroute)** into **T3 Code** as a dedicated provider instance.

---

## 💡 Key Capabilities

1. **Upstream Source Distinction (`--source-tag`)**:
   - Clearly distinguishes between models routed through **Anthropic direct** vs **Antigravity**:
     - `[Anthropic] Claude Sonnet 5.5`
     - `[Antigravity] Claude Sonnet 5.5`
   - Supports 5 customizable tagging formats:
     - `prefix`: `[Anthropic] Claude Sonnet 5.5` *(default)*
     - `short`: `[Claude] Claude Sonnet 5.5` vs `[AG] Claude Sonnet 5.5`
     - `suffix`: `Claude Sonnet 5.5 (Anthropic)` vs `Claude Sonnet 5.5 (Antigravity)`
     - `bullet`: `Anthropic • Claude Sonnet 5.5` vs `Antigravity • Claude Sonnet 5.5`
     - `none`: Clean names without source labels

2. **Reasoning / Thinking Level Grouping**:
   - Rather than creating 5-6 redundant entries in the UI for every model (`-low`, `-medium`, `-high`, `-xhigh`, `-max`), `t3-omniroute-sync` detects these suffixes and collapses them into **one base model** with an interactive **Reasoning (Effort)** selector dropdown directly in T3 Code!

3. **Safe Backups**:
   - Automatic timestamped backups saved to `~/.t3/userdata/settings.json.bak.<timestamp>`.

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

### 3. Sync all Claude models (Anthropic + Antigravity) with prefix tags (Recommended)
```bash
./sync.py --filter "^(claude/|antigravity/.*claude)" --replace
```

### 4. Use different tagging styles
```bash
# Suffix style: Claude Sonnet 5.5 (Antigravity)
./sync.py --filter "^(claude/|antigravity/.*claude)" --source-tag suffix --replace

# Bullet style: Antigravity • Claude Sonnet 5.5
./sync.py --filter "^(claude/|antigravity/.*claude)" --source-tag bullet --replace

# Short style: [AG] Claude Sonnet 5.5 vs [Claude] Claude Sonnet 5.5
./sync.py --filter "^(claude/|antigravity/.*claude)" --source-tag short --replace
```

---

## 🛠️ CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--source-tag <style>` | Tagging style: `prefix`, `short`, `suffix`, `bullet`, `none` | `prefix` |
| `--status` | Print current OmniRoute provider status in T3 Code | — |
| `--list` | Print discovered OmniRoute models without modifying settings | — |
| `--dry-run` | Preview configuration without touching disk | — |
| `--filter <regex>` | Filter model names with a regular expression | `"claude/\|antigravity/.*claude"` |
| `--all` | Include all discovered models (500+) | `False` |
| `--replace` | Overwrite `customModels` instead of merging with existing | `False` |
| `--no-group-thinking` | Keep each thinking level as a separate model entry | `False` (grouped by default) |
| `--base-url <url>` | Override OmniRoute API base URL | Auto-detected from `~/.omniroute/config.json` |
| `--home-path <dir>` | Claude Code home directory for OmniRoute | `~/.claude-omniroute` |
