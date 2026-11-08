#!/bin/sh
# Auditoria de segurança do Raspberry Pi (só leitura: não muda nada). Rode como root no Pi:
#   sh /mnt/dietpi_userdata/folha-domestica/scripts/auditar-pi.sh
PROJ="${PROJ:-/mnt/dietpi_userdata/folha-domestica}"
ok() { echo "  [ok]     $*"; }
alerta() { echo "  [ALERTA] $*"; }
info() { echo "  [info]   $*"; }

echo "== Sistema"
info "$(uname -srm) | Debian $(cat /etc/debian_version) | $(uptime -p)"
n=$(apt list --upgradable 2>/dev/null | grep -c upgradable)
[ "$n" -eq 0 ] && ok "sem atualizações pendentes" || alerta "$n pacotes com atualização pendente (dietpi-update / apt upgrade)"

echo "== Portas abertas para a rede"
ss -H -tulpn | awk '$5 !~ /^(127\.|\[::1\])/ {print "  [info]   " $1, $5, $7}'

echo "== SSH"
if pgrep -x dropbear >/dev/null; then
    args=$(tr '\0' ' ' < /proc/$(pgrep -x dropbear | head -1)/cmdline)
    info "servidor: Dropbear ($args)"
    echo "$args" | grep -q -- " -s" && ok "login por senha desligado (-s)" || alerta "Dropbear aceita login por SENHA (falta -s em /etc/default/dropbear)"
    echo "$args" | grep -q -- " -g" && ok "root só com chave (-g)" || info "root pode entrar com senha se -s não estiver ativo"
elif command -v sshd >/dev/null; then
    cfg=$(sshd -T 2>/dev/null)
    echo "$cfg" | grep -q "^passwordauthentication no" && ok "login por senha desligado" || alerta "OpenSSH aceita login por SENHA"
    info "$(echo "$cfg" | grep -E '^permitrootlogin')"
fi
info "chaves autorizadas do root: $(grep -c . /root/.ssh/authorized_keys 2>/dev/null || echo 0)"

echo "== Senhas padrão do DietPi"
for u in root dietpi; do
    h=$(awk -F: -v u="$u" '$1==u {print $2}' /etc/shadow)
    case "$h" in
        ''|'!'*|'*'*) ok "$u: sem senha utilizável (bloqueado)";;
        *) if python3 - "$h" <<'PY' 2>/dev/null
import sys, crypt
sys.exit(0 if crypt.crypt("dietpi", sys.argv[1]) == sys.argv[1] else 1)
PY
           then alerta "$u ainda usa a senha padrão 'dietpi' (troque com: passwd $u)"
           else ok "$u: senha diferente da padrão (ou formato não verificável)"; fi;;
    esac
done

echo "== Firewall e proteção contra força bruta"
if command -v ufw >/dev/null; then info "$(ufw status | head -1)"; fi
regras=$(iptables -S INPUT 2>/dev/null | grep -vc "^-P")
[ "$regras" -gt 0 ] && info "$regras regras no INPUT do iptables" || info "sem firewall no host (aceitável numa rede doméstica atrás do roteador; NÃO abra portas no roteador)"
command -v fail2ban-client >/dev/null && ok "fail2ban instalado" || info "fail2ban ausente (dispensável se o SSH só aceita chave)"

echo "== Docker"
docker ps --format '  [info]   {{.Names}} {{.Image}} {{.Ports}} {{.Status}}' 2>/dev/null
[ -S /var/run/docker.sock ] && info "socket: $(stat -c '%U:%G %a' /var/run/docker.sock)"
[ -n "$(getent group docker | cut -d: -f4)" ] && alerta "usuários no grupo docker (equivale a root): $(getent group docker | cut -d: -f4)" || ok "ninguém além do root no grupo docker"

echo "== Projeto em $PROJ"
cd "$PROJ" 2>/dev/null || { alerta "pasta do projeto não encontrada"; exit 1; }
p=$(stat -c '%a' .env 2>/dev/null); [ "$p" = "600" ] && ok ".env com permissão 600" || alerta ".env com permissão $p (use: chmod 600 .env)"
chave=$(grep -E '^SECRET_KEY=' .env | cut -d= -f2-)
if [ -z "$chave" ]; then
    [ -s data/secret_key ] && ok "SECRET_KEY gerada pela API em data/secret_key" || info "SECRET_KEY será gerada na próxima subida"
elif [ ${#chave} -lt 32 ] || echo "$chave" | grep -q troque; then
    alerta "SECRET_KEY curta ou de exemplo no .env (a API nova não sobe assim)"
else ok "SECRET_KEY no .env com ${#chave} caracteres"; fi
[ -f data/secret_key ] && { p=$(stat -c '%a' data/secret_key); [ "$p" = "600" ] && ok "data/secret_key com permissão 600" || alerta "data/secret_key com permissão $p"; }
for d in data backups; do
    [ -d "$d" ] && { p=$(stat -c '%a' "$d"); [ "$p" = "700" ] && ok "$d/ com permissão 700" || alerta "$d/ com permissão $p (CPFs e salários: use chmod 700 $d)"; }
done
[ -f certs/servidor.crt ] && info "HTTPS: certificado válido até $(openssl x509 -in certs/servidor.crt -noout -enddate | cut -d= -f2)" || alerta "HTTPS desligado (rode scripts/configurar-https.sh)"
info "cron do root: $(crontab -l 2>/dev/null | grep -v '^#' | grep -c .) tarefa(s)"

echo "== Respostas do site"
curl -s -o /dev/null -w "  [info]   http://localhost -> %{http_code} %{redirect_url}\n" http://localhost/
curl -sk -o /dev/null -w "  [info]   https://localhost -> %{http_code}\n" https://localhost/ 2>/dev/null
curl -sk -I https://localhost/ 2>/dev/null | grep -iE "^(content-security|x-frame|x-content|server):" | sed 's/^/  [info]   /'
code=$(curl -sk -o /dev/null -w "%{http_code}" https://localhost/api/docs); [ "$code" = "404" ] && ok "/api/docs fechado" || info "/api/docs -> $code"
