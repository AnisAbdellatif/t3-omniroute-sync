# t3-omniroute-sync

Connect **[OmniRoute](https://github.com/diegosouzapw/OmniRoute)** to **T3 Code** with a friendly step-by-step wizard.
No packages to install — just Python 3.8+ (already on macOS/Linux).

```bash
python3 sync.py
```

The wizard asks you for:

1. **Your OmniRoute address** — e.g. `192.168.1.20:20128` or `http://localhost:20128`
2. **Your API key** (typing is hidden)
3. **Which providers** you want (arrow keys + `space`, `a` = all, `n` = none, `/` = search)
4. **Which models** you want (Claude models are pre-selected)

Then it creates the `~/claude_omniroute` folder, saves your credentials there (private, mode 600) and adds an
**Omniroute** provider to T3 Code. Open T3 Code's model menu and pick an Omniroute model
(restart T3 Code if it doesn't appear). Your old T3 settings are backed up first
(`~/.t3/userdata/settings.json.bak.<time>`), and nothing is changed if you cancel.

Run it again any time to add or remove models — your address and key are remembered.

## Why you only see models that work

Models come from OmniRoute's **live** `/v1/models` list, not from guesses. Reasoning levels
(`-low`/`-medium`/`-high`…) are folded into one model with a *Reasoning* dropdown only when the plain model really
exists on your server; otherwise each level is listed on its own. This avoids errors like
`Model '…' is not available in the active live catalog`.

## Advanced / scripting

| Option | Meaning |
|---|---|
| `--status` | Show the current T3 Omniroute setup |
| `--dry-run` | Show what would change, write nothing |
| `-y`, `--yes` | No questions; use the flags below |
| `--url`, `--key` | Address / key (key can also come from `OMNIROUTE_API_KEY`) |
| `--providers a,b` | Only these provider ids (e.g. `antigravity,claude`) |
| `--models REGEX` | Only model ids matching this regex (default: Claude models) |
| `--all` | Every model of the chosen providers |
| `--home-path DIR` | Claude config folder (default `~/claude_omniroute`) |
| `--source-tag prefix\|suffix\|none` | Label style, e.g. `[Antigravity] Claude Sonnet 4.6` |
| `--no-group` | Don't fold reasoning levels into one model |

Example: `python3 sync.py -y --url 192.168.1.20 --key sk-… --providers antigravity`
