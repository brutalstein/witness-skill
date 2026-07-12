$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "../../../..") -ErrorAction SilentlyContinue
if ($Root) {
    $Installer = Join-Path $Root "scripts/install-codex.ps1"
    $PyProject = Join-Path $Root "pyproject.toml"
    if ((Test-Path $Installer) -and (Test-Path $PyProject)) {
        & $Installer @args
        exit $LASTEXITCODE
    }
}
Write-Error "This installed skill does not contain the full Witness package. Clone the Witness GitHub repository and run scripts/install-codex.ps1."
exit 2
