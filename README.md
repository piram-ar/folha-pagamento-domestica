# Folha Doméstica

Aplicação local-first para gestão da folha de pagamento de trabalhadores domésticos.
Roda em um Raspberry Pi 3 Model B (SO 64-bit) com Docker: FastAPI + SQLite no backend
e React servido pelo Nginx no frontend.

```
folha-domestica/
├── docker-compose.yml        # orquestração (restart: always + volume do SQLite)
├── .env.example              # configurações (copie para .env)
├── data/                     # database.db fica aqui (volume persistente)
├── scripts/backup.sh         # backup diário do banco
├── backend/
│   ├── alembic/versions/0001_estrutura_inicial.py   # migração que cria as tabelas
│   └── app/
│       ├── models.py         # modelos SQLAlchemy (tabelas)
│       ├── schemas.py        # validação Pydantic (CPF, mês, valores)
│       ├── routers/          # auth, usuarios, trabalhadores, eventos, folha, ferias, inss, notificacoes
│       └── services/
│           ├── calculo_folha.py  # motor de cálculo
│           ├── tabelas.py        # alíquotas de FGTS/encargos e tabela INSS de reserva
│           ├── inss.py           # tabela progressiva do INSS por vigência (cadastrada na tela)
│           ├── pagamentos.py     # datas de pagamento (N-ésimo dia útil / dia do mês)
│           ├── notificacoes.py   # calendário .ics/.vcs e avisos por e-mail
│           ├── salario.py        # salário de cada competência (histórico de reajustes)
│           ├── esocial.py        # rubricas do eSocial doméstico
│           ├── guia_esocial.py   # guia de lançamento da folha no eSocial (PDF/CSV)
│           ├── ferias.py         # períodos aquisitivos
│           └── recibo_pdf.py     # holerite (com vínculo) e recibo de serviços (sem vínculo)
└── frontend/                 # React + Vite, nginx.conf faz proxy de /api
```

## Instalação no Raspberry Pi (DietPi 64-bit)

1. **Primeiro boot:** `ssh root@<ip-do-raspberry>` (senha inicial `dietpi`). O assistente atualiza o
   sistema, pede novas senhas e abre o `DietPi-Software`: marque **Docker** (ID 162) e
   **Docker Compose** (ID 134) e instale. Se pular essa tela: `dietpi-software install 162 134`.
2. **`dietpi-config`:** fuso `America/Sao_Paulo` (o cron do backup usa o relógio do Pi). Reserve o IP
   do Pi no roteador para o endereço não mudar.
3. **Swap:** o DietPi já cria ~1 GB em `/var/swap`, suficiente para o build. Para mudar:
   `/boot/dietpi/func/dietpi-set_swapfile 1536`.
4. **Projeto** (do Windows, sem `node_modules`, `data-local` nem `.env`):

```bash
# no Windows (Git Bash), dentro da pasta do projeto
tar -cf - --exclude=node_modules --exclude=data-local --exclude=.env --exclude=dist \
  --exclude=__pycache__ --exclude=backups --exclude='data/*' --exclude=.venv --exclude=.git --exclude=android . \
  | ssh root@<ip-do-raspberry> 'mkdir -p /mnt/dietpi_userdata/folha-domestica && tar -xf - -C /mnt/dietpi_userdata/folha-domestica --no-same-owner'

# no Pi
cd /mnt/dietpi_userdata/folha-domestica
sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh
cp .env.example .env && chmod 600 .env
nano .env                            # SECRET_KEY (openssl rand -hex 32) e senha do admin
docker compose up -d --build         # o primeiro build no Pi 3 leva de 15 a 30 minutos
```

Em outro Raspberry Pi OS, o Docker vem de `curl -fsSL https://get.docker.com | sh` e o resto é igual.

Acesse `http://<ip-do-raspberry>` de qualquer dispositivo da rede e entre com `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
Depois, cadastre os dados do empregador/contratante e o local da prestação do serviço na tela
**Empregador / Contratante** (eles saem no recibo).

**Reinício automático:** os dois serviços usam `restart: always` e o Docker está habilitado no
systemd, então após um reboot ou queda de energia a aplicação volta sozinha. O banco fica em
`./data/database.db` no host; recriar ou atualizar os containers não apaga os dados.

**Atualizar a aplicação:** copie o projeto de novo com o mesmo comando `tar` acima (ele não toca em
`.env` nem em `data/`) e rode `docker compose up -d --build` no Pi. As migrações rodam automaticamente
na subida do backend.

**Ajustes para o Pi 3 (1 GB de RAM, cartão SD):** a aplicação já vem enxuta: 1 worker do Uvicorn com
pool de 4 threads, migrações no mesmo processo da API, bytecode pré-compilado, biblioteca de PDF
carregada só ao gerar o primeiro recibo, Nginx com 1 worker servindo arquivos pré-comprimidos,
sem access log e sem healthcheck periódico. Limites de memória: 256 MB (backend) e 64 MB (frontend).
Se o primeiro build travar por falta de memória, aumente o swap (passo 3 acima).

**Backup:** `scripts/backup.sh` gera cópias consistentes em `./backups` (mantém as 30 mais recentes).
Agende com `crontab -e` → `0 3 * * * /mnt/dietpi_userdata/folha-domestica/scripts/backup.sh`.

**Cópia para o OneDrive** (cartões SD falham): `scripts\copiar-backups.ps1` busca os backups do Pi por SSH
e grava em `%OneDrive%\Backups\folha-domestica` (registro em `copias.log` na mesma pasta). Para rodar
sozinho todo dia às 9h e a cada login: `powershell -ExecutionPolicy Bypass -File scripts\agendar-copia-backups.ps1`.
No DietPi com Dropbear, o `scp` precisa de `apt install openssh-sftp-server` e
`ln -s /usr/lib/openssh/sftp-server /usr/lib/sftp-server`.

## Testar no Windows antes de implantar no Pi

Requer Python 3.12 e Node.js 20+ (não precisa de Docker). Dê duplo clique em `scripts
odar-local.cmd`
ou rode no terminal:

```bat
scripts
odar-local.cmd               :: desenvolvimento (recarrega ao editar o código)
scripts
odar-local.cmd -Producao     :: testa o build final do frontend, o mesmo que vai para o Pi
scripts
odar-local.cmd -ZerarBanco   :: apaga o banco de testes e começa do zero
scripts
odar-local.cmd -Reinstalar   :: reinstala dependências após mudar requirements.txt/package.json
```

Na primeira vez as dependências são instaladas automaticamente. Abre `http://localhost:5173`
(login padrão `admin@local` / `admin123`, ou o que estiver no `.env`). O banco de testes fica em
`data-local/`, separado do `data/` do Pi. `Ctrl+C` encerra tudo.

## Desenvolvimento local (sem Docker)

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload    # http://localhost:8000/api/docs
cd frontend && npm install && npm run dev                                    # http://localhost:5173
```

## Regras de cálculo

| Item | Regra |
|---|---|
| Salário do mês | mensalista: **mês completo** (todos os dias do mês, seja de 28 ou 31) paga o salário cheio, pelo mês comercial de 30 dias. Mês incompleto (admissão, desligamento, afastamento) é proporcional aos dias reais do mês: `salário ÷ dias do mês × dias trabalhados`. No mês da admissão, a tela já sugere os dias a partir dela |
| Valor-hora | `salário base ÷ divisor de horas` do cadastro (padrão 200 h; a LC 150/2015 permite até 220). Horas extras e atrasos são recalculados ao calcular a folha |
| Hora extra | `valor-hora × (1 + adicional) × horas`, adicional 50% ou 100% |
| Falta | por dias (`salário ÷ dias do mês × dias`) ou por horas (`valor-hora × horas`) |
| Vales/adiantamentos | somados no mês e descontados no fechamento |
| Vale-transporte | cadastrado **por dia** e multiplicado pelos dias úteis do mês: dias da semana trabalhados (configurados no cadastro do trabalhador) sem os feriados nacionais. O número é sugerido na tela da folha e pode ser ajustado (feriado local, falta, folga). A cota do empregado (até 6%) continua sendo um desconto mensal fixo |
| Benefícios fixos | cada um configurado como *soma ao salário*, *desconta do salário* (ex.: cota de 6% do VT) ou *pago à parte* (só informativo no recibo), com **início da vigência**: entra nas folhas a partir do mês dessa data, o que permite gerar folhas e recibos de meses passados só com os benefícios da época |
| **Com registro** | INSS do empregado (tabela progressiva) descontado no recibo. Encargos = estimativa da guia DAE: INSS do empregado + 8% patronal + 0,8% GILRAT + 8% FGTS + 3,2% FGTS compensatório |
| **Sem registro** | Sem descontos legais. "Fundo de reserva" = 1/12 férias + 1/3 de férias + 1/12 13º (≈ 19,44% da remuneração) |
| Férias | 30 dias a cada 12 meses desde a admissão; prazo de concessão de 12 meses após o período; alertas de vencimento |

Folha **fechada** congela os valores e bloqueia lançamentos do mês; apenas admins podem reabri-la.
Ao pagar, marque a folha como **paga** (com a data); a lista "Folhas registradas", no fim da tela da folha,
mostra todas as competências com a situação (paga/em aberto) e o total líquido ainda em aberto.

> ⚠️ **Tabela do INSS:** cadastrada na tela **Tabela do INSS**, uma por vigência (vem com a de 2025).
> Quando o governo publicar a tabela do ano (normalmente em janeiro), cadastre uma nova vigência: cada folha
> usa a tabela válida no seu mês, e folhas fechadas não mudam. IRRF não é calculado.
> Os valores são estimativas para controle: a guia oficial é sempre a emitida pelo eSocial.

## Reajustes salariais

Na aba **Configuração financeira** do trabalhador, registre aumentos por **percentual**, **acréscimo em R$**
ou **novo salário**, a partir de uma competência. Cada folha usa o salário vigente no seu mês (folhas
anteriores ao reajuste não mudam), e um reajuste futuro passa a valer sozinho quando o mês chega. Os
reajustes entram sempre no fim do histórico e só o último pode ser excluído; meses com folha fechada
ficam protegidos.

## Recibos

- **Com vínculo (CLT):** holerite no formato do recibo de salário do eSocial: empregador, empregado, função,
  rubricas com o código do eSocial (ex.: `eSocial1000` Salário, `eSocial5180` INSS), bases de cálculo
  (INSS, FGTS, IRRF) e data preenchida pelo empregado. A via do empregador traz o demonstrativo dos valores
  devidos (estimativa da DAE).
- **Sem vínculo:** recibo simples de prestação de serviços domésticos ("Eu, ..., CPF ..., declaro que recebi
  de ... a importância de R$ ... (valor por extenso)..."), com as duas vias na mesma folha A4.

**eSocial:** o módulo do empregador doméstico não aceita importação de arquivos. Na tela da folha, a
**Guia de lançamento** (PDF ou CSV) lista, por empregado, as rubricas e os valores a digitar em
Folha/Recolhimento. As rubricas seguem o Manual do eSocial do Empregador Doméstico (versão 13/08/2026).

## Avisos de pagamento

No cadastro de cada trabalhador ficam as datas do **salário** (ex.: 5º dia útil) e, se houver acordo, do
**adiantamento** (ex.: dia 20). Dia útil conta de segunda a sábado, sem feriados nacionais; um dia fixo que
cair em domingo ou feriado é antecipado. A tela **Avisos de pagamento** oferece:

- **Agenda (.ics):** eventos que se repetem todo mês, com alarmes na antecedência escolhida (ex.: 3 e 1 dia
  antes). Há também o **.vcs** para agendas antigas (próximos 12 meses) e um **link de assinatura** que se
  atualiza sozinho (só dentro da rede de casa).
- **E-mail:** o Pi verifica a cada 10 minutos e envia um único e-mail com os avisos do dia a partir do horário
  escolhido. Se estiver desligado na hora, envia quando voltar, sem repetir avisos. Gmail/Outlook exigem uma
  *senha de app*. A senha SMTP fica no banco do Pi e nunca é devolvida para a tela.

## App Android

O app **Folha Doméstica** (Capacitor, mesma interface React em modo `app`) cobre a rotina do mês no
celular: início, lançamentos, folha (calcular, fechar e **compartilhar o holerite/recibo pelo WhatsApp,
e-mail etc.**), férias e **avisos de pagamento como notificação**. Cadastros e configurações continuam no
navegador.

- **Instalar:** baixe `https://github.com/piram-ar/folha-pagamento-domestica/releases/latest/download/folha-domestica.apk`
  no celular, abra e permita a instalação. Na primeira abertura, informe o endereço do Pi (ex.: `http://192.168.5.7`).
- **Rede:** o app conversa com o Pi pela rede de casa (HTTP). O backend libera CORS só para a origem do app.
- **Avisos no celular:** em **Mais > Avisos neste celular**. O app busca no Pi os pagamentos dos próximos
  120 dias e agenda notificações locais (mesma antecedência e horário do e-mail). Elas tocam com o app fechado
  e fora de casa; a agenda se refaz sempre que o app é aberto no Wi-Fi de casa.
- **Build:** o GitHub Actions (`.github/workflows/app-android.yml`) gera o APK a cada mudança em `frontend/`
  e publica uma release. A assinatura usa uma chave fixa guardada nos segredos do repositório; para criá-la,
  rode uma vez `bash scripts/configurar-assinatura-android.sh` (a cópia local fica em `~/.android-chaves`).
  Sem a chave, o workflow gera só um APK de teste (artefato), sem release.
- **Desenvolvimento:** `npm run build:app` gera o modo app e sincroniza o projeto `frontend/android`.

## Aparência

Modo claro, escuro ou conforme o sistema, no rodapé do menu lateral (ou em **Mais** no celular). A escolha
vale por aparelho.

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).
