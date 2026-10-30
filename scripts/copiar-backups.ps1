# Copia os backups do banco do Raspberry Pi para o OneDrive (o OneDrive sincroniza com a nuvem).
# Roda pelo Agendador de Tarefas do Windows (ver README); também pode ser executado à mão.
# Só copia; nunca apaga nada no Pi nem no OneDrive.
param(
    [string]$Pi = "root@192.168.5.7",
    [string]$Chave = "$env:USERPROFILE\.ssh\folha_pi",
    [string]$Destino = "$env:OneDrive\Backups\folha-domestica"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Destino | Out-Null
$log = Join-Path $Destino "copias.log"

& "$env:WINDIR\System32\OpenSSH\scp.exe" -q -p -i $Chave -o BatchMode=yes -o ConnectTimeout=15 `
    "${Pi}:/mnt/dietpi_userdata/folha-domestica/backups/database-*.db" "$Destino\"

if ($LASTEXITCODE -eq 0) {
    $qtd = (Get-ChildItem $Destino -Filter "database-*.db").Count
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  ok, $qtd backups em $Destino" | Add-Content $log -Encoding utf8
} else {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  FALHOU (Pi desligado ou fora da rede?) codigo $LASTEXITCODE" | Add-Content $log -Encoding utf8
    exit 1
}
