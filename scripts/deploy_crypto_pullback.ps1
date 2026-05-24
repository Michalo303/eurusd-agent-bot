param(
    [string]$HostName = "91.99.99.158",
    [string]$User = "root",
    [string]$RemoteDir = "/opt/trading/crypto-pullback"
)

$ErrorActionPreference = "Stop"
$target = "${User}@${HostName}"

Write-Host "==> Preparing remote directory"
ssh $target "mkdir -p ${RemoteDir}"

Write-Host "==> Uploading crypto_freqtrade package"
scp -r crypto_freqtrade/* "${target}:${RemoteDir}/"

Write-Host "==> Starting crypto pullback dry-run"
ssh $target "cd ${RemoteDir} && mkdir -p user_data/logs user_data/data user_data/backtest_results && chmod -R a+rwX user_data && docker compose up -d"

Write-Host "==> Status"
ssh $target "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -E 'crypto-pullback|eurusd-worker|NAMES'"
