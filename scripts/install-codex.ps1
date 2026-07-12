$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $ScriptDir "install_codex.py"
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Installer --repo-root $RepoRoot @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Installer --repo-root $RepoRoot @args
} else {
    throw "Python 3.11+ is required."
}
exit $LASTEXITCODE
