# t3-omniroute-sync

Use your **[OmniRoute](https://github.com/diegosouzapw/OmniRoute)** models inside **T3 Code**, set up by a short guided wizard.

- **Zero dependencies.** Python 3.8+ standard library only.
- **Live catalog.** Models come from your server's `/v1/models`, so you only see models that work.
- **Safe.** Your T3 settings are backed up first, written atomically, and left untouched if you cancel.
- **Re-runnable.** Run it again any time to add or remove models. Your address and key are remembered.

## Quick start

```bash
git clone https://github.com/AnisAbdellatif/t3-omniroute-sync.git
cd t3-omniroute-sync
python3 sync.py
```

Open T3 Code at least once beforehand so its settings file exists. After the wizard finishes, pick an **Omniroute** model in T3 Code's model menu. Restart T3 Code if it doesn't appear.

You can also install it as a command:

```bash
uv tool install .      # or: pipx install .
t3-omniroute-sync
```

## What the wizard asks

| Step | Question |
|---|---|
| 1 | **OmniRoute address**, e.g. `192.168.1.20`, `localhost:20128` or `http://host:20128`. The default port is added for you. |
| 1 | **API key**. Typing is hidden, and a saved key can be reused with Enter. |
| 2 | **Claude config folder**, default `~/claude_omniroute`. |
| 3 | **Providers**, with Claude-serving providers pre-selected. |
| 4 | **Models**, with Claude models pre-selected. |
| – | **Name style**: how the provider appears in model names (see below). |
| 5 | **Review and apply**. |

Checklist keys: `↑`/`↓` move, `space` ticks, `a` all, `n` none, `/` search, `enter` done, `q` cancel. Terminals without curses get a numbered fallback.

### What gets written

| File | Change |
|---|---|
| `~/.t3/userdata/settings.json` | Adds or updates an `omniroute` provider instance (backup: `settings.json.bak.<time>`, last 10 kept). Other settings are preserved. |
| `<folder>/settings.json` | Holds `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`. The file is mode `600` and the folder mode `700`. |
| `<folder>/{skills,commands,agents,CLAUDE.md}` | Automatically symlinked from `~/.claude` so all your custom skills, slash commands, agents, and instructions remain available. |

## Name styles

Choose how the provider is shown in the model menu:

| Style | Example |
|---|---|
| `prefix` (default) | `[Antigravity] Claude Sonnet 5.5` |
| `short-prefix` | `[AG] Claude Sonnet 5.5` |
| `suffix` | `Claude Sonnet 5.5 (Antigravity)` |
| `short-suffix` | `Claude Sonnet 5.5 (AG)` |
| `none` | `Claude Sonnet 5.5` |

Short codes: `AG` Antigravity, `A` Anthropic, `OAI` OpenAI, `G` Gemini, `GH` GitHub, `CX` Codex, `OR` OpenRouter, `DS` DeepSeek. Unknown providers use their initials.

## Reasoning levels

OmniRoute lists reasoning variants as separate models (`-low`, `-medium`, `-high`, `-xhigh`, `-max`). The wizard folds them into **one model with a *Reasoning* dropdown**, but only when the plain model really exists on your server. Otherwise each level stays its own entry. This avoids T3 sending a name OmniRoute doesn't serve (`Model '…' is not available in the active live catalog`). Use `--no-group` to keep every level separate.

## Command-line options

| Option | Meaning |
|---|---|
| `--status` | Show the current Omniroute setup in T3 and exit |
| `--dry-run` | Show what would change, write nothing |
| `-y`, `--yes` | No questions; use flags and defaults |
| `--url`, `--key` | Address and key. The key can also come from `OMNIROUTE_API_KEY`. |
| `--providers a,b` | Only these provider ids, e.g. `antigravity,claude` |
| `--models REGEX` | Only model ids matching this regex (default: Claude models) |
| `--all` | Every model of the chosen providers |
| `--home-path DIR` | Claude config folder (default `~/claude_omniroute`) |
| `--no-link` | Don't symlink skills, commands, and agents from `~/.claude` |
| `--source-tag STYLE` | `prefix`, `short-prefix`, `suffix`, `short-suffix` or `none` |
| `--no-group` | Don't fold reasoning levels into one model |
| `--version` | Print the version |

Non-interactive example:

```bash
OMNIROUTE_API_KEY=sk-… python3 sync.py -y --url 192.168.1.20 \
  --providers antigravity --source-tag short-prefix
```

## Troubleshooting

- **"Couldn't find T3 Code's settings"**: open T3 Code once, then re-run.
- **"OmniRoute rejected the API key"**: create or copy a key in the OmniRoute dashboard under *API Keys*.
- **Models don't show up**: restart T3 Code.
- **Undo**: restore the newest `~/.t3/userdata/settings.json.bak.*` file.

## Development

```bash
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE) © Anis Abdellatif
