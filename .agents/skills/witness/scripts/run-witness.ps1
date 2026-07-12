$ErrorActionPreference = "Stop"
$Command = Get-Command witness -ErrorAction SilentlyContinue
if ($Command) {
    & $Command.Source @args
    exit $LASTEXITCODE
}
$Launcher = Join-Path $HOME ".local/bin/witness.cmd"
if (Test-Path $Launcher) {
    & $Launcher @args
    exit $LASTEXITCODE
}
Write-Error "Witness is not installed. Run the repository's scripts/install-codex.ps1 first."
exit 2
