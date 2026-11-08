#!/bin/sh
# Liga o HTTPS na rede de casa com uma autoridade certificadora (CA) própria.
#
#   cd /mnt/dietpi_userdata/folha-domestica && sh scripts/configurar-https.sh [IP] && docker compose up -d
#
# - A CA fica em /root/folha-ca (chave legível só pelo root, fora do projeto e dos containers).
#   Ela só pode assinar certificados para a rede de casa (name constraints: 192.168.0.0/16, *.local, *.lan
#   e o nome do Pi). Mesmo que a chave vazasse, não serviria para se passar por bancos ou outros sites.
# - O certificado do servidor vai para ./certs (lido pelo Nginx). Vale 825 dias; rodar de novo renova
#   reaproveitando a mesma CA, então os aparelhos não precisam reinstalar nada.
# - Instale /root/folha-ca/folha-ca.crt (também copiada para ./certs/folha-ca.crt) como certificado
#   confiável em cada computador e celular que acessa o sistema. Veja o README, seção HTTPS.
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
CA_DIR="${FOLHA_CA_DIR:-/root/folha-ca}"
IP="${1:-$(hostname -I | awk '{print $1}')}"
NOME="$(hostname)"
umask 077
mkdir -p "$CA_DIR" "$DIR/certs"

if [ ! -s "$CA_DIR/folha-ca.key" ]; then
    echo ">> Criando a autoridade certificadora da casa em $CA_DIR"
    cat > "$CA_DIR/ca.cnf" <<CNF
[req]
distinguished_name = dn
prompt = no
x509_extensions = ext
[dn]
CN = Folha Domestica - CA da rede de casa ($NOME)
O = Folha Domestica
[ext]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
nameConstraints = critical, permitted;IP:192.168.0.0/255.255.0.0, permitted;IP:10.0.0.0/255.0.0.0, permitted;DNS:$NOME, permitted;DNS:.local, permitted;DNS:.lan, permitted;DNS:localhost
CNF
    openssl req -x509 -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 -days 3650 \
        -keyout "$CA_DIR/folha-ca.key" -out "$CA_DIR/folha-ca.crt" -config "$CA_DIR/ca.cnf"
fi

echo ">> Emitindo o certificado do servidor para $IP, $NOME e $NOME.local"
cat > "$CA_DIR/servidor.cnf" <<CNF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = $NOME
[ext]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = IP:$IP, DNS:$NOME, DNS:$NOME.local, DNS:localhost
authorityKeyIdentifier = keyid
subjectKeyIdentifier = hash
CNF
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 \
    -keyout "$DIR/certs/servidor.key" -out "$CA_DIR/servidor.csr" -config "$CA_DIR/servidor.cnf"
openssl x509 -req -in "$CA_DIR/servidor.csr" -CA "$CA_DIR/folha-ca.crt" -CAkey "$CA_DIR/folha-ca.key" \
    -CAcreateserial -days 825 -sha256 -extfile "$CA_DIR/servidor.cnf" -extensions ext -out "$DIR/certs/servidor.crt"
# Cadeia completa (servidor + CA) para clientes que não têm a CA intermediária em cache
cat "$CA_DIR/folha-ca.crt" >> "$DIR/certs/servidor.crt"
cp "$CA_DIR/folha-ca.crt" "$DIR/certs/folha-ca.crt"
# O Nginx do container lê como outro usuário: certificados legíveis, chave só do root (o master do Nginx roda como root)
chmod 644 "$DIR/certs/servidor.crt" "$DIR/certs/folha-ca.crt"
chmod 600 "$DIR/certs/servidor.key"
rm -f "$CA_DIR/servidor.csr"

openssl verify -CAfile "$CA_DIR/folha-ca.crt" "$DIR/certs/servidor.crt" >/dev/null
echo ">> Pronto. Impressão digital da CA (confira ao instalar nos aparelhos):"
openssl x509 -in "$CA_DIR/folha-ca.crt" -noout -fingerprint -sha256
echo ">> Agora: docker compose up -d   (o Nginx liga o HTTPS ao encontrar ./certs/servidor.crt)"
