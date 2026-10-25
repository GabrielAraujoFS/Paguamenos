# Progresso do frontend

Última atualização: 2026-10-25. Este arquivo registra entregas, verificações e pendências. Fundação, catálogo, briefing e listagem de campanhas estão implementados; detalhes persistidos, validação e revisão permanecem para as próximas etapas.

## Análise e planejamento

- [x] Inventariar os arquivos existentes em `docs/` e preservar os arquivos do repositório.
- [x] Ler `API_CONTRACT.md`, `FRONTEND_HANDOFF.md`, `FRONTEND_IMPLEMENTATION_PLAN.md` e inspecionar rotas/schemas de `openapi.json`.
- [x] Identificar sete operações, entidades públicas, regras de estado, ausência de autenticação/perfis e lacunas de API.
- [x] Definir arquitetura, páginas, componentes e fluxos em `FRONTEND_ARCHITECTURE.md`.
- [x] Definir etapas e critérios em `FRONTEND_ROADMAP.md`.
- [x] Criar instruções permanentes em `AGENTS.md`.

## Implementação

- [x] Identidade visual Zyntra AI: logos horizontal clara/escura e símbolo adicionados; paleta azul-marinho, azul e laranja, tokens de interface e Geist aplicados ao layout e às telas existentes.
- [x] `npm run build` e `npm run lint` após a atualização visual — ambos concluídos sem erros.
- [ ] Verificação visual da nova identidade em navegador/telas pequenas — pendente nesta sessão.

- [x] Etapa 0 — Fundação técnica: React/TypeScript/Vite, Tailwind CSS, shadcn/ui, React Router, TanStack Query, Axios, RHF/Zod, configuração de ambiente, layout e estados comuns.
- [ ] Fechar integração da etapa 0 com backend vivo no navegador (`GET /health`, `GET /products` e CORS); o acesso HTTP ao backend não pôde ser confirmado nesta sessão.
- [x] Etapa 1 — Catálogo e briefing: listagem/detalhe via API, seleção de produto, formulário validado, envio de `GenerateRequest` e confirmação com ID da campanha.
- [x] Listagem de campanhas — rota `/campanhas`, pesquisa, filtro por estado de peça, paginação e atualização via `GET /campaigns`.
- [x] Etapa 2 — Geração e consulta por ID: cartões clicáveis e link após geração abrem `/campaigns/:campaignId`, com briefing e todas as peças.
- [x] Etapa 3 — Validação da campanha: POST sem body, estado atual, resultados por severidade e histórico.
- [x] Etapa 4 — Revisão por peça: identificação, comentário, confirmação, bloqueio de aprovação incompatível e atualização do cache; 409 reconsulta a campanha.
- [ ] Etapa 5 — Responsividade, acessibilidade e estados de erro.
- [ ] Etapa 6 — Conveniência local opcional, se aprovada como útil.

## Testes e verificações

- [x] Documentação estática: inventário de rotas e schemas do OpenAPI comparado com os documentos de contrato.
- [x] `npm install` das dependências de runtime e desenvolvimento; shadcn/ui inicializado pelo CLI; `package-lock.json` gerado.
- [x] `npm run lint` — sem erros nem avisos.
- [x] `npm run build` — checagem TypeScript e build Vite concluídos.
- [x] `npm run dev` — Vite informou pronto em `http://localhost:5173/`; a execução com `--host 127.0.0.1` também iniciou.
- [ ] Sondagem HTTP do servidor de desenvolvimento — a requisição entre sessões expirou por restrição de acesso a socket do ambiente; a inicialização foi confirmada pelo log do Vite.
- [x] `npm run test` — 4 testes passaram: entradas inválidas, payload exato, mapeamento de 422 e preservação do briefing com retry explícito após 502.
- [x] `npm run lint` e `npm run build` após o módulo — ambos passaram.
- [x] Backend real em modo mock com SQLite temporário, sem alterar seu repositório: TestClient confirmou 200 (`/health`, `/products`, detalhe), 404 (`PRODUCT_NOT_FOUND`), 422 (`INVALID_REQUEST`), 201 (geração), preflight CORS 200 e igualdade do OpenAPI vivo com `docs/openapi.json`.
- [x] Axios contra backend temporário em HTTP: 200 para saúde, catálogo e detalhe; 201 para geração; preço permaneceu string e peça retornou `draft`.
- [ ] Teste integrado e inspeção visual no navegador com backend mock — o navegador incorporado retornou `ERR_CONNECTION_TIMED_OUT` para `http://localhost:5173`; checagens HTTP e CORS isoladas passaram.
- [x] Verificar CORS e igualdade do OpenAPI vivo com o snapshot por TestClient.
- [x] Testes de atualização de cache — validação substitui campanha; revisão substitui apenas a peça retornada; conflito 409 reconsulta o estado.
- [ ] Teste responsivo e de acessibilidade — interface ainda não implementada.

## Pendências e bloqueios documentados

- [x] Confirmar acesso HTTP temporário ao backend real em `127.0.0.1:8000` e CORS para `http://localhost:5173`; falta validar a interface no navegador com ambos os servidores ativos.
- [x] Registrar divergência entre documentação anterior e API viva antes de adaptar contratos; snapshot OpenAPI atualizado.
- [ ] Obter contratos de autenticação/perfis se o produto exigir acesso controlado; hoje as sete operações são públicas.
- [x] Confirmar API de listagem/pesquisa: `GET /campaigns` disponível no backend local.
- [ ] Obter contratos de edição/regeneração, mídia/publicação, regras/produtos administráveis e métricas se essas funções forem requisitadas.
- [ ] Definir hospedagem e CORS de produção com o backend; a configuração documentada é local.

## Registro de alterações

### Fluxo de gerenciamento de campanhas — 2026-10-25

- Cartões navegáveis e link após geração para `/campaigns/:campaignId`; detalhe consulta a API, apresenta briefing e conteúdo integral de cada peça.
- Validação sem body, última execução e histórico de resultados, severidades e estado atual do servidor. HTTP 200 com bloqueios críticos permanece resultado de negócio, sem marcar aprovação.
- Revisão por peça com React Hook Form/Zod, identificação de 1–100 caracteres, comentário de até 2000, confirmação explícita, proteção de envios concorrentes e ausência de retry automático. Aprovação depende de estado `validated` e última validação bem-sucedida; rejeição é permitida nos estados documentados.
- Cache por campanha atualizado com respostas reais; listas invalidadas após operações; 409 força nova consulta. Falha na consulta após conflito mostra erro e impede ações sobre dados antigos. Erro de rede orienta atualizar antes de repetir uma operação cujo resultado não foi confirmado.
- Contratos confrontados com as rotas do OpenAPI vivo em `127.0.0.1:8000`; sem novos endpoints nem alteração de backend, OpenAPI ou Docker.
- Dependências instaladas com `npm ci --no-audit --no-fund`, sem mudança no lockfile. Verificações usaram o Node 24.22.1 fornecido pelo aplicativo; Node 22.14 do terminal é inferior aos requisitos de algumas dependências atuais.
- TypeScript (`tsc -b`), build de produção (`vite build`) e lint (`eslint .`) passaram.
- Suíte Vitest: **17 testes passaram, 1 teste opt-in ignorado**. Execução final com `vitest run --maxWorkers=1 --testTimeout=20000`; execução concorrente com o build havia provocado timeouts em testes preexistentes. Nenhum teste preexistente foi alterado.
- Teste opt-in HTTP: **1 passou**, executado separadamente com `ZYNTRA_TEST_LIVE_API=1` e `VITE_API_BASE_URL=http://127.0.0.1:8769`. Usa os serviços frontend contra FastAPI temporário, provedor mock explícito e SQLite descartável: catálogo, geração de duas peças, aprovação bloqueada antes da validação (409), validação, aprovação, rejeição, persistência e busca. Não usa Gemini nem banco da demonstração.
- Fixtures de componentes cobrem navegação pelo cartão, conteúdo completo, regras críticas e avisos, revisão confirmada/cancelada, cache, identificação obrigatória, conflito 409, erros 404/422/502, rede e proteção contra duplo envio. Teste de serviços confirma URLs com IDs codificados e POST de validação sem body.
- Pendente: inspeção visual e fluxo manual no navegador em telas pequenas e grandes; os testes HTTP não equivalem a um teste completo de navegador nem a uma avaliação da geração Gemini.

### Divergência confirmada antes da tela de campanhas (2026-10-24)

O backend local em `http://127.0.0.1:8000/openapi.json` expõe `GET /campaigns`, ausente no snapshot e planejamento anteriores. A rota não usa prefixo `/api`. Aceita `page` (mínimo 1, padrão 1), `page_size` (1–100, padrão 20), `status` (`PieceState`), `channel` (`Channel`) e `search` (string não vazia). Retorna `CampaignPage` com `items: Campaign[]`, `total`, `page`, `page_size` e `total_pages`. Uma consulta real devolveu esse envelope com uma campanha e `total: 1`; filtro combinado `status=approved&search=algodão` devolveu lista vazia e `total: 0`. Não há status agregado, atualização ou descrição própria de campanha no schema; os estados pertencem às peças. Não há parâmetro de ordenação. `docs/openapi.json` foi atualizado a partir do OpenAPI vivo após a confirmação.

| Data | Alteração | Verificação | Pendência |
|---|---|---|---|
| 2026-10-25 | Adicionadas as três logos Zyntra AI, tokens de cor da marca, tipografia Geist, cabeçalho com logo clara sobre azul-marinho e cores coordenadas nas telas/componentes existentes. | `npm run build` e `npm run lint` passaram. | Verificar contraste e encaixe do cabeçalho em navegador e viewport pequeno. |
| 2026-10-24 | Análise dos quatro arquivos preexistentes em `docs/`; criação de `AGENTS.md`, arquitetura, roadmap e checklist. | Leitura dos documentos e inspeção de rotas/schemas OpenAPI. | Confirmar API viva. |
| 2026-10-24 | Fundação React/Vite, dependências, Tailwind/shadcn, navegação, cliente HTTP, diagnóstico real e estados compartilhados. | Instalação concluída; lint e build passaram; Vite iniciou na porta 5173. | Confirmar GETs e CORS com backend vivo; implementar catálogo e briefing na próxima etapa. |
| 2026-10-24 | Catálogo, detalhe do produto e briefing com geração; navegação, estados de carregamento/erro/vazio, validação de campos e tratamento de 404/422/502. | 4 testes passaram; lint/build passaram; TestClient e Axios confirmaram API real, CORS e OpenAPI com banco temporário. | O navegador incorporado não alcançou Vite local; conferir visualmente no navegador do usuário. Próximo módulo: detalhes de campanha por ID. |
| 2026-10-24 | Adicionado build Docker com Nginx, proxy `/api` para o backend e URL relativa no cliente; Compose na raiz sobe os dois serviços. | `npm run lint`, `npm run build` e `docker compose config` passaram. | Teste de subida com Docker pendente: o daemon do Docker Desktop não estava ativo nesta sessão. |
| 2026-10-24 | Tela `/campanhas` com busca por nome e filtro por estado no servidor, paginação, resumo das peças, atualização, estados de espera/erro/vazio; contrato e arquitetura atualizados. | OpenAPI vivo e duas respostas reais consultados; 7 testes automatizados passaram; lint e build passaram. | A rota de detalhes frontend ainda não existe; sem ordenação ou status agregado no contrato. Inspeção visual no navegador permanece pendente. |
