"""Client for the Hermes Agent API server in the NemoClaw sandbox.

Hermes exposes an OpenAI-compatible API on port 8642, behind a gateway token.
The token comes from EL_HERMES_TOKEN when set (a container, the hosted demo),
otherwise from `nemohermes <sandbox> gateway-token`. It is never logged.
"""
from __future__ import annotations

import subprocess

import httpx

from el.areas import AreaIndex

SANDBOX_VAULT = "/sandbox/Documents/Obsidian Vault"
_TOKEN_SCRIPT = (
    'export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh" >/dev/null 2>&1; '
    'nemohermes "$1" gateway-token --quiet'
)


class HermesError(RuntimeError):
    pass


def vault_map(index: AreaIndex) -> str:
    """A short guide to the vault, so Hermes reads the right files instead of guessing paths."""
    lines = [
        "You are E-L, the user's personal assistant. Their Obsidian vault is at "
        f"{SANDBOX_VAULT} (a read-only snapshot; do not edit it).",
        "Areas and where their notes live:",
    ]
    for area in index.areas:
        places = [*area.backlogs, *(f"{folder}/" for folder in area.folders)]
        lines.append(f"- {area.name}: {', '.join(places) or 'nothing yet'}")
    lines.append("Open tasks are `- [ ]` lines, mostly in the Backlog/ files. Answer briefly and name the notes you used.")
    return "\n".join(lines)


class Hermes:
    def __init__(self, base_url: str, sandbox: str, token: str | None = None, timeout: float = 300):
        self.base_url = base_url
        self.sandbox = sandbox
        self._token = token
        self.timeout = timeout

    def _get_token(self) -> str:
        if self._token:
            return self._token
        try:
            result = subprocess.run(
                ["bash", "-c", _TOKEN_SCRIPT, "_", self.sandbox],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HermesError(f"Couldn't run nemohermes to get the gateway token: {exc}") from exc
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if result.returncode != 0 or not lines:
            raise HermesError(f"nemohermes gave no gateway token for sandbox '{self.sandbox}'.")
        self._token = lines[-1]
        return self._token

    def ask(self, question: str, system: str = "") -> str:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": question})
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._get_token()}"},
                json={"model": "hermes-agent", "messages": messages},
                timeout=self.timeout,
            )
        except httpx.ConnectError as exc:
            raise HermesError(
                "Hermes isn't reachable on port 8642. In Ubuntu, run: nemohermes "
                f"{self.sandbox} recover"
            ) from exc
        except httpx.HTTPError as exc:
            raise HermesError(f"Request to Hermes failed: {exc}") from exc
        if response.status_code == 401:
            self._token = None
            raise HermesError("Hermes rejected the gateway token. Try again; it will be fetched afresh.")
        if response.status_code != 200:
            raise HermesError(f"Hermes returned HTTP {response.status_code}.")
        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise HermesError("Hermes sent a reply E-L couldn't read.") from exc
