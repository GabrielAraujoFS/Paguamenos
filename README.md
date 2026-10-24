# Creative Factory + Brand Guardian

Aplicação de hackathon para transformar briefings de marketing em variações de
campanha, verificar dados e regras objetivas e encaminhar as peças à revisão humana.
Entrega prevista: **26/10/2026**. O repositório compartilhado deverá ser **privado**,
administrado por Gabriel ou pela organização da equipe.

## Estrutura

```text
backend/
  app/          API, contratos, persistência, serviços e dados sintéticos
  tests/        testes com SQLite isolado
  examples/     briefing, respostas e OpenAPI exportado
  docs/         orientação de integração
  README.md     instalação, execução e roteiro completo do Swagger
paguemenos-FRONT-END/  interface React + TypeScript
compose.yaml            API, frontend e volume SQLite
```

O frontend está em `paguemenos-FRONT-END/`. A documentação específica permanece
junto a cada serviço.

## Executar todo o projeto com Docker

Com o Docker Desktop ativo, execute na raiz:

```powershell
docker compose up --build -d
```

Se o projeto estiver no OneDrive e o build falhar com `invalid file request`,
use `./scripts/compose-up.ps1` no PowerShell. O script copia os contextos de build
para uma pasta temporária, executa o Compose e apaga a cópia ao terminar. Isso
evita os pontos de nova análise criados pelo OneDrive em arquivos do projeto.

- Interface: [http://localhost:5173](http://localhost:5173)
- Swagger da API: [http://localhost:8000/docs](http://localhost:8000/docs)
- A interface acessa a API pelo proxy `/api` do Nginx; o navegador não precisa
  chamar a porta 8000 diretamente.
- O banco SQLite fica no volume `backend_data` e sobrevive a `docker compose down`.
- Para parar: `docker compose down`. Para apagar também os dados locais do volume:
  `docker compose down -v`.

O provedor padrão é `mock`, sem chave ou serviço externo. Para usar Gemini, copie
`.env.example` para `.env`, defina `GENERATION_PROVIDER=gemini` e preencha
`GEMINI_API_KEY`; depois recrie os contêineres com o comando acima (ou com o
script, se estiver no OneDrive).
O arquivo `.env` é ignorado pelo Git. As portas 5173 e 8000 são publicadas somente
em `127.0.0.1`; se estiverem ocupadas, ajuste o lado esquerdo dos mapeamentos em
`compose.yaml`.

## Executar o backend

Pré-requisitos: Python **3.13**, acesso ao índice de pacotes para instalar as
dependências e permissão de escrita no diretório do projeto e na pasta temporária
do sistema. Após a instalação, a execução não depende de serviços externos.

PowerShell, a partir da raiz deste projeto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O SQLite é criado automaticamente. As configurações opcionais estão em
[backend/.env.example](backend/.env.example); arquivos `.env` não são carregados
automaticamente. A origem React padrão é `http://localhost:5173`.

Na pasta `backend`, execute os testes:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Consulte o [guia do backend](backend/README.md) para configuração detalhada,
estados e roteiro de testes manuais.

Os 27 testes originais são preservados, com novos testes de configuração,
expressões, severidades e geração. Dois avisos conhecidos neste ambiente são:
`StarletteDeprecationWarning` pelo uso de HTTPX
0.28.1 com o TestClient do Starlette 1.8.0 e `PytestCacheWarning` por falta de
permissão de escrita no cache local. Nenhum invalida os testes. A compatibilidade
do cliente de testes deve ser revista antes de atualizar dependências; não foi
adicionada outra biblioteca nesta preparação. Para executar sem o cache opcional,
use `python -m pytest -q -p no:cacheprovider` com o Python do ambiente virtual.
O SQLite temporário dos testes ainda precisa de uma pasta temporária gravável.

As dependências diretas têm versões fixadas em `backend/requirements.txt`; as
transitivas ainda não têm um arquivo de lock. Não há caminhos pessoais obrigatórios,
credenciais ou banco pré-existente necessários à execução. Os comandos acima são
para Windows; em Linux/macOS use `python3.13` e o executável `.venv/bin/python`.

## Integração e situação atual

- [Swagger local](http://127.0.0.1:8000/docs) e
  [OpenAPI em execução](http://127.0.0.1:8000/openapi.json).
- [Contratos para Alexsandro](backend/docs/integracao.md),
  [OpenAPI exportado](backend/examples/openapi.json) e
  [exemplos completos](backend/examples/responses.json).
- Funciona: catálogo sintético, geração textual mock, validação objetiva,
  aprovação/rejeição humana, histórico e persistência em SQLite.
- Configuração textual de marca e campanha, expressões por canal, alertas e
  checagem comercial nos formatos suportados: [guia](backend/docs/configuracao.md).
- Gemini opcional por configuração, com mock como padrão:
  [configuração, nível gratuito e limitações](backend/docs/geracao-ia.md).
- Sprint 3: geração real com Gemini, validação e aprovação humana verificadas
  pelo responsável pelo backend no Swagger; 117 testes automatizados cobrem
  também falhas simuladas e bloqueios críticos, sem chamadas externas.
- Pendente: frontend, integração React, decisões de Emily sobre regras e dados
  autorizados.

As regras são provisórias e sintéticas; não representam regras oficiais de marcas
reais. Não há publicação automática. Preços/ofertas vêm do catálogo, e os preços
trafegam como strings decimais. Alterações de contrato devem ser alinhadas com
Alexsandro antes de integrar.

## Colaboração até 26/10

Use `main` como versão integrada e executável, com branches curtas por tarefa:
`codex/backend-<tarefa>`, `frontend/<tarefa>` e `docs/<tarefa>`. Não é necessário
manter uma branch `develop` neste hackathon.

Abra PRs pequenos para `main`, com objetivo, arquivos/contratos afetados e como
testar. Uma revisão de outro integrante e os testes pertinentes são suficientes;
Gabriel pode configurar proteção de `main` quando criar o repositório. A suíte
de backend deve passar antes de integrar. Não há CI configurada nesta etapa.

Atualize a branch com `main` antes de abrir o PR, combine mudanças em arquivos
compartilhados e integre com frequência. Para mudanças de API, atualize os
exemplos/OpenAPI exportado e avise Alexsandro. Quando frontend e backend estiverem
juntos, valide o fluxo gerar → validar → revisar. Prefira squash merge para manter
o histórico simples; a equipe pode adotar o merge padrão se já houver preferência.

## Primeiro versionamento e futuro remoto

**O repositório Git local está inicializado nesta pasta, na branch `main`.**
O repositório do projeto é independente de eventuais repositórios em pastas superiores.
Os arquivos necessários estão preparados para staging; o primeiro commit ainda
depende de autorização. Não é necessário alterar configurações globais.

Após autorização, na raiz `projeto-hacka-business`, os comandos recomendados são:

```powershell
git rev-parse --show-toplevel
git status --short --untracked-files=all
git check-ignore .venv backend/creative_factory.db backend/.env
git add .gitignore README.md backend
git diff --cached --stat
git diff --cached --name-only
git diff --cached
git commit -m "chore: adiciona backend MVP e documentação"
```

Confirme que `--show-toplevel` aponta exatamente para esta pasta. Antes do commit,
revise o conteúdo preparado: sem `.venv`, `.env`, bancos, caches ou credenciais.
`backend/.env.example`, os JSON sintéticos e os exemplos da API devem ser incluídos.
Se faltar identidade de autor, configure `user.name` e `user.email` apenas com
`git config --local`, usando seus dados reais.

Gabriel deve criar um repositório **privado e vazio**, sem README, licença ou
`.gitignore` automáticos, e conceder acesso à equipe. Depois de confirmar a URL,
e com autorização para publicar:

```powershell
git remote add origin URL_PRIVADA_FORNECIDA_POR_GABRIEL
git remote -v
git push -u origin main
```

Substitua o marcador pela URL real; não coloque tokens na URL. Autentique pelo
gerenciador de credenciais ou SSH da sua máquina. Se o remoto já tiver commits,
não use force push: alinhe com Gabriel e prefira clonar o repositório da equipe
em outra pasta e copiar apenas os arquivos destinados ao versionamento.

Após o primeiro envio, Alexsandro poderá clonar o mesmo repositório e trabalhar
em sua branch de frontend. Estes comandos são instruções futuras: nenhum commit,
remoto ou envio faz parte desta preparação.
