# Electron desktop testing

Electron projects are detected from `package.json` and use `ElectronAdapter`. Witness launches
the application with a loopback-only Chromium remote-debugging port, connects Playwright over
CDP, and reuses the WebAdapter's accessible locators, screenshots, DOM geometry, console errors,
network failures, downloads, dialogs, and visual heuristics.

Typical configuration:

```yaml
project:
  type: desktop
  start: npm run start
  # Optional deterministic port. If omitted, Witness reserves a free loopback port.
  electron_debug_port: 9222
  # Keep cookies/local storage away from the developer's normal Electron profile.
  electron_isolated_profile: true
```

The launch command may include `{debug_port}` explicitly:

```yaml
project:
  start: npx electron . --remote-debugging-port={debug_port}
```

For npm/pnpm/yarn scripts, Witness appends the Chromium flag after `--`. Native OS dialogs,
system keychains, and privileged main-process APIs are not silently automated; expose explicit
test seams or use a platform-specific adapter for those boundaries.


## Security and determinism

Witness chooses a free loopback port unless a deterministic port is configured, binds Chromium debugging to `127.0.0.1`, and launches with an isolated `electron-user-data` directory inside the output folder by default. This avoids reusing the developer's real cookies, local storage, extensions, or cached credentials. Set `electron_isolated_profile: false` only for an explicitly reviewed test profile.

CDP controls renderer windows, not privileged operating-system surfaces. Native file pickers, keychains, updater prompts, tray menus, and main-process-only behavior need a project-owned test seam or a dedicated platform driver. Witness does not silently enable global desktop input injection.
