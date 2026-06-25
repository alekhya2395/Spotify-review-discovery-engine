# Sync GROQ_API_KEY from project .env to Railway (run from repo root).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) {
    Write-Error ".env not found at $envFile"
}

$key = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^GROQ_API_KEY=(.+)$') {
        $key = $matches[1].Trim().Trim('"').Trim("'")
    }
}

if (-not $key) {
    Write-Error "GROQ_API_KEY is empty in .env"
}

Write-Host "Linking Railway project (pick the Spotify backend service when prompted)..."
Set-Location $root
railway link

Write-Host "Setting Railway variables..."
$key | railway variable set GROQ_API_KEY --stdin
railway variable set GROQ_CHAT_MODEL=llama-3.1-8b-instant
railway variable set CHAT_STABLE_MODE=false
railway variable set ALLOWED_ORIGINS=https://spotify-review-discovery-engine-alekhyadhulipudi.vercel.app

Write-Host "Done. Verify: https://spotify-review-discovery-engine-production.up.railway.app/api/health"
