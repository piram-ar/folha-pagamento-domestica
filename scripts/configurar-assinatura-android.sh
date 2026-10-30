#!/bin/sh
# Cria a chave que assina o app Android e a cadastra como segredo do repositório no GitHub.
# Rode UMA vez, no seu computador:  bash scripts/configurar-assinatura-android.sh
# Requer: keytool (vem com o Java), openssl e o GitHub CLI (gh) logado.
set -e
DIR="$HOME/.android-chaves"
CHAVE="$DIR/folha-domestica.p12"
if [ -e "$CHAVE" ]; then
  echo "A chave já existe em $CHAVE. Para recadastrar os segredos, apague o arquivo só se souber o que está fazendo."
  exit 1
fi
mkdir -p "$DIR" && chmod 700 "$DIR"
SENHA=$(openssl rand -hex 16)
keytool -genkeypair -storetype PKCS12 -keystore "$CHAVE" -alias folhadomestica -keyalg RSA -keysize 2048 \
  -validity 10000 -storepass "$SENHA" -keypass "$SENHA" -dname "CN=Folha Domestica, C=BR" >/dev/null 2>&1
printf 'Chave de assinatura do app Folha Doméstica\nArquivo: folha-domestica.p12\nAlias: folhadomestica\nSenha: %s\n\nGuarde o arquivo e a senha (ex.: num gerenciador de senhas). Sem eles, versões novas do app\nnão instalam por cima da atual e seria preciso desinstalar e instalar de novo.\n' "$SENHA" > "$DIR/LEIA-ME.txt"
chmod 600 "$DIR"/*
base64 -w0 "$CHAVE" | gh secret set ANDROID_KEYSTORE_BASE64
printf '%s' "$SENHA" | gh secret set ANDROID_KEYSTORE_PASSWORD
printf 'folhadomestica' | gh secret set ANDROID_KEY_ALIAS
echo "Pronto. Chave salva em $DIR e segredos cadastrados no GitHub:"
gh secret list
