# Agenda scripts\copiar-backups.ps1 no Agendador de Tarefas do Windows:
# todo dia às 9h (ou assim que o PC ligar, se estava desligado) e a cada login.
# Para remover: Unregister-ScheduledTask -TaskName "Folha Domestica - copiar backups do Pi"
$script = Join-Path $PSScriptRoot "copiar-backups.ps1"
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$gatilhos = @((New-ScheduledTaskTrigger -Daily -At 9am), (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME))
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "Folha Domestica - copiar backups do Pi" -Action $acao -Trigger $gatilhos -Settings $config `
    -Description "Copia os backups do banco do Raspberry Pi para o OneDrive" -Force | Select-Object TaskName, State
