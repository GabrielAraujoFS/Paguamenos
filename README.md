# Creative Factory + Brand Guardian

Aplicação de hackathon para transformar briefings de marketing em variações de
campanha, verificar dados e regras objetivas e encaminhar as peças à revisão humana.
Entrega: **26/10/2026**. O projeto reúne API e frontend no mesmo repositório.

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

As dependências diretas do backend estão em `backend/requirements.txt`; as
transitivas não têm arquivo de lock. Consulte os READMEs de cada serviço para
requisitos e verificações atualizados.

## Integração e situação atual

- [Swagger local](http://127.0.0.1:8000/docs) e
  [OpenAPI em execução](http://127.0.0.1:8000/openapi.json).
- [Contratos para Alexsandro](backend/docs/integracao.md),
  [OpenAPI exportado](backend/examples/openapi.json) e
  [exemplos completos](backend/examples/responses.json).
- Funciona: catálogo sintético, geração de campanhas, validação objetiva,
  aprovação/rejeição humana, histórico e persistência em SQLite.
- Configuração textual de marca e campanha, expressões por canal, alertas e
  checagem comercial nos formatos suportados: [guia](backend/docs/configuracao.md).
- Gemini opcional por configuração, com mock como padrão:
  [configuração, nível gratuito e limitações](backend/docs/geracao-ia.md).
- O frontend integra catálogo, briefing, histórico, detalhe, validação, revisão
  humana e prévia de peças renderizadas; veja
  [progresso do frontend](paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md).
- Antes da entrega, falta validar o fluxo visual no navegador e subir o Compose
  com o Docker Desktop ativo. Provedores Google/OpenAI dependem de chaves.

As regras são provisórias e sintéticas; não representam regras oficiais de marcas
reais. Não há publicação automática. Preços/ofertas vêm do catálogo, e os preços
trafegam como strings decimais. Alterações de contrato devem ser alinhadas com
Alexsandro antes de integrar.

## Documentação por área

- [Backend: instalação, API e fluxo no Swagger](backend/README.md)
- [Frontend: instalação e comandos](paguemenos-FRONT-END/README.md)
- [Contrato e handoff da integração](docs/FRONTEND_HANDOFF.md)
- [Composição de imagens e provedores visuais](backend/docs/composicao.md)

O modo padrão usa provedores mock/disabled e funciona sem chaves externas. As
chaves configuradas no `.env` não devem ser incluídas na entrega.
