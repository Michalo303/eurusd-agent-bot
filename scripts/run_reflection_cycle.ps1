param(
    [switch]$Apply,
    [switch]$Deploy,
    [string]$Csv = "data\eurusd_5m.csv",
    [string]$CommitPrefix = "Reflect strategy"
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "==> $Message"
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & python @Args
}

Write-Step "Refreshing PATH and tokens"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$env:RAILWAY_API_TOKEN = [System.Environment]::GetEnvironmentVariable("RAILWAY_API_TOKEN", "User")
$env:PYTHONPATH = "src"
Remove-Item Env:RAILWAY_TOKEN -ErrorAction SilentlyContinue

if (-not (Test-Path $Csv)) {
    Write-Step "Fetching Yahoo EURUSD data"
    Invoke-Python -m eurusd_bot fetch-yahoo --out $Csv
}

Write-Step "Running reflection"
$reflectArgs = @("-m", "eurusd_bot.reflect", "--csv", $Csv)
if ($Apply) {
    $reflectArgs += "--apply"
}
$reflectionJson = Invoke-Python @reflectArgs
if ($LASTEXITCODE -ne 0) {
    throw "Reflection command failed"
}
$reflectionJson | Tee-Object -FilePath "state\last_reflection.json"
$reflection = $reflectionJson | ConvertFrom-Json

if (-not $reflection.applied) {
    Write-Step "No strategy change applied"
    exit 0
}

$changed = $reflection.changed_variable
$oldValue = $reflection.old_value
$newValue = $reflection.new_value
Write-Step "Applied one-variable change: $changed $oldValue -> $newValue"

Write-Step "Running tests"
Invoke-Python -m pytest

Write-Step "Running backtest with updated strategy"
Invoke-Python -m eurusd_bot backtest --csv $Csv --db logs\journal.sqlite
Invoke-Python -m eurusd_bot export-journal --db logs\journal.sqlite --out-dir logs\export

$message = "${CommitPrefix}: $changed $oldValue -> $newValue"

Write-Step "Committing strategy change"
git add state\strategy.yaml state\history state\hypotheses.jsonl state\last_reflection.json
git commit -m $message

Write-Step "Pushing to GitHub"
git push

if ($Deploy) {
    Write-Step "Deploying to Railway"
    railway up --detach --message $message
    Write-Step "Waiting for worker logs"
    Start-Sleep -Seconds 45
    railway logs --lines 120
}
