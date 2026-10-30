# Sobe a aplicação no Windows (sem Docker) para testar antes de implantar no Raspberry Pi.
#
#   scripts\rodar-local.cmd               -> modo desenvolvimento (recarrega ao editar o código)
#   scripts\rodar-local.cmd -Producao     -> testa o build final do frontend (o mesmo que vai para o Pi)
#   scripts\rodar-local.cmd -ZerarBanco   -> apaga o banco de testes e começa do zero
#   scripts\rodar-local.cmd -Reinstalar   -> reinstala as dependências (após mudar requirements/package.json)
#
# O banco de testes fica em data-local\ (separado do data\ usado no Pi). Ctrl+C encerra tudo.
param([switch]$Producao, [switch]$ZerarBanco, [switch]$Reinstalar)
$ErrorActionPreference = 'Stop'

$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz 'backend'
$frontend = Join-Path $raiz 'frontend'
$dados = Join-Path $raiz 'data-local'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'

foreach ($cmd in 'python', 'node', 'npm') {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "'$cmd' não encontrado no PATH. Instale Python 3.12 e Node.js 20+."
    }
}

# 1. Dependências (só na primeira vez ou com -Reinstalar)
if ($Reinstalar -or -not (Test-Path $python)) {
    Write-Host '>> Instalando dependências do backend...' -ForegroundColor Cyan
    if (-not (Test-Path $python)) { python -m venv (Join-Path $backend '.venv') }
    & $python -m pip install -q --disable-pip-version-check -r (Join-Path $backend 'requirements.txt')
    if ($LASTEXITCODE) { throw 'Falha ao instalar as dependências do backend.' }
}
if ($Reinstalar -or -not (Test-Path $vite)) {
    Write-Host '>> Instalando dependências do frontend...' -ForegroundColor Cyan
    Push-Location $frontend
    try { npm ci --no-audit --no-fund; if ($LASTEXITCODE) { throw 'Falha no npm ci.' } } finally { Pop-Location }
}

# 2. Configuração: usa o .env (se existir), mas sempre com o banco de testes
$arquivoEnv = Join-Path $raiz '.env'
if (Test-Path $arquivoEnv) {
    foreach ($linha in Get-Content $arquivoEnv -Encoding UTF8) {
        if ($linha -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim()
        }
    }
}
if ($ZerarBanco -and (Test-Path $dados)) {
    Remove-Item -Recurse -Force $dados
    Write-Host '>> Banco de testes apagado.' -ForegroundColor Yellow
}
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $dados 'database.db').Replace('\', '/')

# 3. Backend (as migrações e o admin inicial são criados na subida)
$argsApi = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000')
if (-not $Producao) { $argsApi += '--reload' }
$api = Start-Process -FilePath $python -ArgumentList $argsApi -WorkingDirectory $backend -NoNewWindow -PassThru

try {
    Write-Host '>> Aguardando a API...' -ForegroundColor Cyan
    $pronta = $false
    for ($i = 0; $i -lt 60 -and -not $api.HasExited; $i++) {
        try { Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; $pronta = $true; break }
        catch { Start-Sleep -Seconds 1 }
    }
    if (-not $pronta) { throw 'A API não subiu. Veja as mensagens acima.' }

    $usuario = if ($env:ADMIN_EMAIL) { $env:ADMIN_EMAIL } else { 'admin@local' }
    $senha = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { 'admin123' }
    Write-Host ''
    Write-Host "  Aplicação:  http://localhost:5173   (login: $usuario / $senha)" -ForegroundColor Green
    Write-Host '  API (docs): http://localhost:8000/api/docs' -ForegroundColor Green
    Write-Host "  Banco:      $dados\database.db" -ForegroundColor Green
    Write-Host '  Ctrl+C para encerrar.' -ForegroundColor Green
    Write-Host ''

    # 4. Frontend (o /api é encaminhado para a porta 8000 pelo vite.config.js)
    Push-Location $frontend
    try {
        if ($Producao) {
            node $vite build
            if ($LASTEXITCODE) { throw 'Falha no build do frontend.' }
            node $vite preview --port 5173 --strictPort --open
        } else {
            node $vite --port 5173 --strictPort --open
        }
    } finally { Pop-Location }
}
finally {
    # Encerra a API e os processos filhos (o --reload cria um processo extra)
    if (-not $api.HasExited) { taskkill /PID $api.Id /T /F | Out-Null }
}
