param(
    [Parameter(Mandatory = $true)]
    [string]$HostName,

    [string]$User = "root",
    [string]$AppDir = "/opt/eurusd-agent-bot",
    [string]$RepoUrl = "https://github.com/Michalo303/eurusd-agent-bot.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$target = "${User}@${HostName}"
$remoteScript = "/tmp/hetzner_bootstrap.sh"

Write-Host "==> Uploading bootstrap script to $target"
scp scripts/hetzner_bootstrap.sh "${target}:${remoteScript}"

Write-Host "==> Running bootstrap on Hetzner"
ssh $target "chmod +x ${remoteScript} && APP_DIR='${AppDir}' REPO_URL='${RepoUrl}' BRANCH='${Branch}' bash ${remoteScript}"

Write-Host "==> Done. Useful commands:"
Write-Host "ssh $target 'cd ${AppDir} && docker compose ps'"
Write-Host "ssh $target 'cd ${AppDir} && docker compose logs -f eurusd-worker'"

