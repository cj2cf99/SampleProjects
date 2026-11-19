$ErrorActionPreference = 'Stop'
$gamePort = if ($env:PORT) { [int]$env:PORT } else { 8786 }
$gameUrl = "http://127.0.0.1:$gamePort/"
$startedModel = $null

function Test-LocalModel {
    try {
        (Invoke-RestMethod -Uri 'http://127.0.0.1:18786/health' -TimeoutSec 2).status -eq 'ok'
    } catch { $false }
}

Push-Location $PSScriptRoot
try {
    if (!$env:AI_BASE_URL -and !(Test-LocalModel)) {
        $binary = if ($env:LLAMA_SERVER) { $env:LLAMA_SERVER } else { Join-Path $PSScriptRoot '.runtime/llama/llama-server.exe' }
        $weights = if ($env:TAROT_MODEL_FILE) { $env:TAROT_MODEL_FILE } else { 'G:/t2t/qwen3-8b-ft-q4_k_m.gguf' }
        if (!(Test-Path -LiteralPath $binary -PathType Leaf) -or !(Test-Path -LiteralPath $weights -PathType Leaf)) {
            throw 'Set LLAMA_SERVER and TAROT_MODEL_FILE to local files, or set AI_BASE_URL and AI_MODEL for your API.'
        }
        $alias = if ($env:AI_MODEL) { $env:AI_MODEL } else { 'tarot-local' }
        $arguments = @('--model', ('"{0}"' -f $weights), '--alias', ('"{0}"' -f $alias), '--host', '127.0.0.1', '--port', '18786', '--ctx-size', '4096', '--parallel', '1', '--threads', '8', '--reasoning-budget', '0', '--no-webui', '--log-disable')
        $startedModel = Start-Process -FilePath $binary -ArgumentList $arguments -WindowStyle Hidden -PassThru
        $deadline = (Get-Date).AddMinutes(2)
        while (!(Test-LocalModel)) {
            if ($startedModel.HasExited -or (Get-Date) -gt $deadline) { throw 'Local model did not become ready.' }
            Start-Sleep -Seconds 1
        }
    }
    $existing = try { (Invoke-WebRequest -UseBasicParsing -Uri $gameUrl -TimeoutSec 2).Content } catch { '' }
    if ($existing -match 'Nocturne Tarot') {
        Write-Output $gameUrl
        if ($startedModel) { $startedModel.WaitForExit() }
    } else {
        node server.mjs
        if ($LASTEXITCODE) { throw "Game server exited with status $LASTEXITCODE." }
    }
} finally {
    if ($startedModel -and !$startedModel.HasExited) { $startedModel.Kill() }
    Pop-Location
}
