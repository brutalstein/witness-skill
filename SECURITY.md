# Security Policy

## Reporting a vulnerability

Please report security issues privately to the repository maintainers rather than opening a public issue. Include the affected version, reproduction steps, impact, and any suggested mitigation. Maintainers should acknowledge reports promptly and coordinate disclosure after a fix is available.

## Execution model

Witness intentionally starts project processes, drives a browser, and executes model-selected CLI commands inside the selected project directory. Its command denylist and same-origin browser policy are guardrails, not a sandbox or security boundary.

- Run untrusted projects in a disposable container or virtual machine.
- Use a clean branch or throwaway checkout with least-privilege credentials.
- Do not expose production secrets to the target process or Witness environment.
- Keep production testing disabled unless the exact target and impact have been explicitly authorized.
- Review `logs/session_trace.json`, process logs, terminal transcripts, and screenshots before sharing artifacts; typed action payloads are redacted from the trace, but target applications can still echo sensitive values into their own output.
- Treat `--agent-command` for both reasoning and remediation as trusted code. Copy isolation limits accidental project edits but does not prevent a malicious local process from accessing the host. Use a disposable container/VM for untrusted commands.
- Review `remediation.patch` and verification output before using `--apply`. Source application is explicit and gated, but verification commands themselves may execute arbitrary project code.


## Electron and native game bridges

- ElectronAdapter exposes CDP only on a randomly selected loopback port and uses a disposable user-data directory by default. Do not disable profile isolation when the application could access real cookies, local storage, extensions, or credentials.
- `witness-game.json` bridge directories are constrained to the project or Witness output tree unless an explicitly trusted caller enables an external bridge.
- Game manifest loader-injection variables (`LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `PYTHONPATH`, `NODE_OPTIONS`, and related paths) are rejected. The remaining environment applies only to the child game process.
- Unity/Unreal bridges expose named reversible actions, not arbitrary code execution. Do not bind a named action to developer consoles, account deletion, production administration, or unrestricted scripting.
- A file bridge removes the need for an unauthenticated network listener, but the tested game process and repository are still trusted code. Run unknown builds in a disposable VM/container and use isolated test services.

## Codex authentication and native sessions

- Native Codex host mode does not receive or persist an OpenAI credential. The already-running Codex task performs reasoning and submits strict decisions through the local `witness session` CLI.
- `--provider codex-cli` calls `codex login status` and `codex exec`; Witness never opens or copies the Codex credential cache.
- The native daemon binds only to `127.0.0.1`, protects requests with a random bearer token, writes active state with user-only permissions where supported, rejects stale turn submissions, and removes the token when the session ends.
- Keep `witness-output/.witness/session.json` private while a session is active. Do not publish an active output directory.
- Personal ChatGPT-managed Codex credentials should not be copied into untrusted CI runners. Follow the current Codex automation guidance for CI/CD.

Supported releases receive security fixes on the latest `1.x` line until a formal long-term-support policy is published.
