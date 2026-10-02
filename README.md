# Caderno de Casa

App web (Flask) para controlar custos fixos, custos variáveis, receitas e
poupança da casa — pensado para abrir pelo Safari nos dois iPhones e ver os
mesmos dados em tempo real, porque tudo é guardado numa planilha do Google
Sheets.

## Como funciona

- O **banco de dados é a própria planilha**: cada aba (`Receitas`,
  `CustosFixos`, `CustosVariaveis`, `Config`) é lida e escrita por um
  pequeno script (`apps_script.gs`) publicado **de dentro da própria
  planilha**, usando o Google Apps Script — um recurso gratuito do Google
  Sheets que não passa pelo Google Cloud Console e não pede cartão/
  faturamento. O servidor Flask conversa com esse script por HTTP.
- O front-end (pasta `static/`) é o mesmo visual que você já viu, só que em
  vez de salvar no navegador, ele chama a API do Flask (`/api/...`), que por
  sua vez chama o Apps Script, que lê/escreve na planilha.
- Os dois iPhones apontam para a **mesma URL** (o domínio onde o app estiver
  hospedado) e cada um atualiza a tela sozinho a cada ~8s, além de atualizar
  na hora sempre que você mesmo lança algo.
- Sem a planilha configurada, o app roda com dados de exemplo em memória (só
  para testar localmente) — é o que usei para conferir que tudo funciona
  antes de te passar os arquivos.
- **Tudo gratuito**: Google Sheets, Apps Script, hospedagem (plano free do
  Render) e o domínio você já tem no Cloudflare.

## Passo 1 — Criar a planilha

1. Crie uma planilha nova no Google Sheets (pode começar vazia — o app cria
   as abas `Receitas`, `CustosFixos`, `CustosVariaveis` e `Config`
   automaticamente na primeira vez que rodar).
2. Guarde o link dela — vamos usar na planilha mesmo, não precisa copiar
   nenhum ID por enquanto.

## Passo 2 — Publicar o Apps Script (sem Google Cloud, sem cartão)

1. Na planilha, vá em **Extensões → Apps Script**. Abre um editor numa aba
   nova, já vinculado a essa planilha.
2. Apague o conteúdo do arquivo `Código.gs` que abrir e cole o conteúdo
   inteiro do arquivo [`apps_script.gs`](apps_script.gs) deste projeto.
3. Troque a linha `var TOKEN = "troque-por-uma-senha-longa-só-sua";` por uma
   senha longa e aleatória só sua (ex. gere uma em
   [1password.com/password-generator](https://1password.com/password-generator)
   ou simplesmente invente uma frase longa sem espaços). Guarde esse valor —
   é o `SHEETS_WEBAPP_TOKEN` que o app vai usar.
4. Clique em **Salvar** (ícone de disquete).
5. Clique em **Implantar → Nova implantação**. Em "Selecionar tipo", escolha
   **Aplicativo da Web**. Configure:
   - **Executar como**: Eu (seu e-mail)
   - **Quem pode acessar**: Qualquer pessoa
6. Clique em **Implantar**. Na primeira vez, o Google vai pedir para
   autorizar o script a acessar a própria planilha — é uma tela de
   consentimento do seu próprio Google, não cobra nada nem pede cartão;
   clique em **Avançado → Acessar [nome do projeto] (não seguro)** se ele
   avisar que o app não foi verificado (é esperado, porque é um script seu,
   não publicado para terceiros).
7. Copie a **URL do aplicativo da Web** que aparece (termina em `/exec`) —
   é o `SHEETS_WEBAPP_URL`.

Guardou os dois valores (`SHEETS_WEBAPP_URL` e `SHEETS_WEBAPP_TOKEN`)? São
eles que vão no `.env` (local) ou nas variáveis de ambiente do Render
(produção).

> Se um dia precisar alterar o script, lembre de **Implantar → Gerenciar
> implantações → editar (ícone de lápis) → Nova versão → Implantar** — só
> salvar no editor não atualiza a versão publicada.

## Passo 3 — Rodar localmente (opcional, para testar antes de publicar)

```bash
cd caderno-de-casa
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env e preencha:
#   SHEETS_WEBAPP_URL=<a URL do Passo 2>
#   SHEETS_WEBAPP_TOKEN=<o token do Passo 2>

python app.py
# abre em http://localhost:5000
```

Se quiser só testar a interface sem configurar a planilha ainda, rode
`python app.py` sem preencher o `.env` — ele usa dados de exemplo em memória
automaticamente.

## Passo 4 — Publicar no Render com o domínio do Cloudflare

O app roda num host que executa Python (Render), e o **Cloudflare continua só
cuidando do domínio/DNS** — não precisa mexer na conta Cloudflare além do
passo de DNS no final. Essa combinação funciona bem e não exige reescrever
nada do app.

### 4.1 — Subir o código para o GitHub

Já deixei a pasta como repositório git local (primeiro commit feito). Falta
só criar o repositório remoto e enviar:

```bash
cd caderno-de-casa
# crie um repositório vazio no GitHub (pelo site, ou com `gh repo create` se
# tiver o GitHub CLI instalado e autenticado) e depois:
git remote add origin <URL do repositório que você criou>
git branch -M main
git push -u origin main
```

O `.gitignore` já exclui `.env` — seu token não vai para o GitHub. O
`apps_script.gs` pode ir tranquilo (ele só tem um placeholder de token, você
edita o valor real direto no editor do Apps Script, não neste arquivo).

### 4.2 — Criar o Web Service no Render

1. Em [render.com](https://render.com), crie uma conta (dá pra entrar com o
   GitHub) e clique em **New → Web Service**, apontando para o repositório
   que você acabou de subir.
2. Configuração do serviço:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app`
   - **Plan**: o free tier funciona para uso de uma casa; ele "dorme" após
     ficar um tempo sem acesso e demora alguns segundos pra acordar no
     próximo acesso — se isso incomodar, dá pra trocar pro plano pago
     (Starter) depois, sem mudar nada no código.
3. Em **Environment**, adicione as variáveis:
   - `SHEETS_WEBAPP_URL` = a URL copiada no Passo 2
   - `SHEETS_WEBAPP_TOKEN` = o token que você criou no Passo 2
4. Deploy. Quando terminar, o Render te dá uma URL tipo
   `caderno-de-casa.onrender.com` — confirme que abre e funciona antes de
   seguir para o domínio.

### 4.3 — Apontar seu domínio do Cloudflare para o Render

1. No Render, vá em **Settings → Custom Domains → Add Custom Domain** e
   digite o subdomínio que você quer usar, por exemplo
   `casa.seudominio.com.br` (evite usar o domínio raiz puro — com subdomínio
   é mais simples). O Render mostra um registro **CNAME** parecido com
   `caderno-de-casa.onrender.com`.
2. No painel do **Cloudflare**, abra seu domínio → **DNS → Records → Add
   record**:
   - Type: `CNAME`
   - Name: `casa` (ou o subdomínio que você escolheu)
   - Target: o endereço `*.onrender.com` que o Render te deu
   - **Proxy status: DNS only (nuvem cinza, não laranja)** — isso é
     importante na primeira configuração, porque com o proxy da Cloudflare
     ligado (nuvem laranja) o Render não consegue emitir o certificado HTTPS
     automático do domínio. Depois que o Render confirmar o domínio como
     verificado (ele mostra "Verified" no painel), você pode religar o
     proxy se quiser os benefícios da Cloudflare — mas para um app pessoal
     de uso doméstico, deixar "DNS only" já é suficiente e mais simples.
3. Aguarde a propagação (geralmente minutos) e acesse
   `https://casa.seudominio.com.br` — deve abrir o app com certificado
   válido.

## Passo 5 — Usar nos dois iPhones

1. No Safari de cada iPhone, abra o domínio configurado.
2. Toque em **Compartilhar → Adicionar à Tela de Início** — o app passa a
   abrir em tela cheia, com ícone, como um app nativo.
3. Pronto: qualquer lançamento feito em um aparelho aparece no outro em até
   ~8 segundos (ou na hora, se for você mesmo lançando).

## Estrutura da planilha

| Aba | Colunas |
|---|---|
| `Receitas` | id, nome, valor |
| `CustosFixos` | id, categoria, nome, valor |
| `CustosVariaveis` | id, categoria, nome, valor, data |
| `Config` | chave, valor — `period`, `savingsPercent`, `savingsBalance`, `investmentBalance`, `variableBudget` |

Você pode abrir a planilha a qualquer momento para conferir ou exportar os
dados — ela é a fonte da verdade, o app só lê e escreve nela.

## Limites a saber

- O plano gratuito do Apps Script (contas pessoais do Google) aguenta tranquilamente
  o uso de uma casa com dois celulares — o gargalo seria só em uso muito
  mais pesado que esse.
- O app guarda os dados lidos em cache por 4 segundos para não bater na
  planilha a cada toque de tela.
- A segurança do Apps Script é o **token**: qualquer um que souber a URL e o
  token consegue ler/editar a planilha por essa ponte — por isso use uma
  senha longa e aleatória no `TOKEN` do `apps_script.gs`, e não a compartilhe
  fora do `.env`/variáveis de ambiente do Render.
- Se um dia quiser trocar o token, basta editar a constante `TOKEN` no
  editor do Apps Script, publicar uma nova versão (veja o aviso no Passo 2)
  e atualizar `SHEETS_WEBAPP_TOKEN` no `.env`/Render.
