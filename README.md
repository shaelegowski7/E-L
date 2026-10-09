# E-L

An always-on, private personal AI assistant. Built for the **Nebius x NVIDIA Global AI Hackathon** (Personal AI track).

E-L keeps everything in an Obsidian vault: projects, tasks, deadlines and session notes. It shows them on one dashboard: a Today page plus a page per area of your life. Its agent, Hermes, answers questions about the vault using NVIDIA Nemotron, and runs inside an NVIDIA OpenShell sandbox that can't touch your real files.

> Work in progress. The Today page and Ask E-L work; the morning brief, write-back and Daily life integrations are next.

## How it works

```
Obsidian vault ──► E-L web app (FastAPI) ──► Today page, area pages
      │                     │
      │ sync_vault.sh       │ Ask E-L (OpenAI-compatible API, port 8642)
      ▼                     ▼
  copy of the notes ◄── Hermes Agent ──► Nemotron 3 Super on Nebius Token Factory
  └──────── inside an NVIDIA OpenShell sandbox, set up by NemoClaw ────────┘
```

- **Figures and lists come straight from the vault.** The web app reads the vault directly for counts, dates and task lists, so no model is involved and they're always exact.
- **Questions go to Hermes.** It answers with Nemotron 3 Super through Nebius Token Factory, reading the vault with its Obsidian skill.
- **The sandbox never sees the real vault.** `scripts/sync_vault.sh` copies the notes in, and while the app runs it re-syncs whenever a note changes (checked every 2 minutes and before each question). OpenShell limits the sandbox to that folder and an approved list of network destinations, and API keys stay outside it.

## Stack

- NVIDIA Nemotron 3 Super (main) and Nemotron 3 Nano (bulk jobs), via Nebius Token Factory
- Hermes Agent (Nous Research), run by NVIDIA NemoClaw inside NVIDIA OpenShell
- Python, FastAPI and Jinja templates; `uv` for dependencies
- Nebius Serverless for the hosted demo (planned)

## Setup (Windows with WSL2)

1. **WSL2 and Docker:** install Ubuntu in WSL2 and Docker Desktop, then turn on Docker's WSL integration for Ubuntu. NemoClaw needs at least 8 GB of memory; give WSL more in `%USERPROFILE%\.wslconfig` if needed:
   ```ini
   [wsl2]
   memory=10GB
   swap=8GB
   ```
2. **NemoClaw with Hermes,** inside Ubuntu, using Nemotron 3 Super on Token Factory:
   ```bash
   export NEMOCLAW_AGENT=hermes NEMOCLAW_SANDBOX_NAME=e-l NEMOCLAW_PROVIDER=custom
   export NEMOCLAW_ENDPOINT_URL=https://api.tokenfactory.nebius.com/v1
   export NEMOCLAW_MODEL=nvidia/nemotron-3-super-120b-a12b
   export COMPATIBLE_API_KEY=<your Nebius Token Factory key>
   curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
   ```
3. **Settings:** copy `.env.example` to `.env` and fill in `NEBIUS_API_KEY` and `EL_VAULT`, the WSL path to your vault, such as `/mnt/c/Users/<you>/<vault>`.
4. **Run, inside Ubuntu,** after installing [uv](https://docs.astral.sh/uv/):
   ```bash
   bash scripts/test.sh   # tests, against a small made-up vault in tests/fixtures
   bash scripts/dev.sh    # serves http://127.0.0.1:8000 and keeps the sandbox's vault copy current
   ```

If Ask E-L says Hermes isn't reachable, run `nemohermes e-l recover` in Ubuntu. It restores the port forward after a restart.

## Vault conventions E-L reads

- **Tasks:** `- [ ]` and `- [x]` lines. Put `📅 YYYY-MM-DD` on a task to give it a due date.
- **Events:** notes in `Calendar/` with `date`, `title` and an optional `area` in their frontmatter, the format the Full Calendar plugin uses.
- **Sessions:** Claude Log entries (`type: claude-log`) and project session notes (`type: session`).
- **Areas:** the defaults are in `el/areas.py`. A ```yaml block in the vault note `E-L/Areas.md` overrides them.

## Licence

MIT. See [LICENSE](LICENSE).
