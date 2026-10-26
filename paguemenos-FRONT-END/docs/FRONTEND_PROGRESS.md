# Progresso do frontend

## BrandGuard visual (2026-10-25)

- O painel de validação existente na campanha classifica o relatório em **Conforme**, **Não conforme** ou **Revisão necessária**, usando `ValidationRun.success`, `severity` e `passed`. Exibe as regras visuais e mensagens de evidência recebidas da API, sem criar endpoint ou esquema novo no frontend.
- O backend estendeu o fingerprint aos bytes da imagem final, sidecars, fundo, cópia persistida do produto, fotografia oficial, logo e fonte; aprovação antiga é invalidada quando eles mudam. Verificação final: 184 testes de backend e 15 de frontend aprovados; `npm run lint` e `npm run build` aprovados.

## Integração híbrida em 2026-10-25

- Divergência confirmada: a documentação anterior descrevia apenas campanhas textuais, mas o OpenAPI vivo e os módulos `render.py`, `schemas` e `storage.py` oferecem plano visual, render assíncrono e referências de imagem. O backend recebeu `GET /pieces/{piece_id}/image`; os snapshots OpenAPI do backend e deste frontend foram atualizados.
- Implementada a tela `/campanhas/:campaignId`: consulta campanha e estado de cada peça, mostra dados comerciais autorizados, plano visual, metadados, validações e histórico de revisão. Ações de render usam `request_id`, consultas periódicas só ocorrem em `processing` e `background_ready`, e a prévia PNG usa URL de objeto revogada ao desmontar. Mutação de validação/revisão não tem retry automático e usa trava contra clique duplo.
- Verificação final: backend `pytest` 173 aprovados; frontend `npm run test` 14 aprovados, `npm run lint` e `npm run build` aprovados; `docker compose config --quiet` aprovado. O teste de clique duplo revelou uma validação duplicada após resposta rápida; a trava recebeu janela curta de 800 ms e os testes de validação e revisão passaram novamente.
- Pendências: testar navegação no navegador com backend e frontend ligados, executar Docker Compose com daemon ativo e validar provedor pago somente com autorização de custo. O backend ainda não possui autenticação/autorização; a prévia e as mutações não podem ser expostas publicamente sem proteção.

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

### Fallback explícito de IA — 2026-10-26

- Serviços existentes inspecionados antes da alteração: mock textual, carregador local e compositor reutilizados; não havia continuação explícita após falha. Nenhum provedor foi substituído globalmente e nenhum fallback é disparado automaticamente.
- Textos: erro temporário/429 fornece oferta vinculada ao briefing/produto/regras. Somente o botão **Continuar com versão demonstrativa** repete a requisição com demo_token e usa o mock. O formulário preserva dados e **Retomar briefing** permite nova tentativa posterior. Origem persistida e identificada na confirmação, nos cartões e no detalhe; campanhas legadas têm origem não registrada.
- Imagens: somente **Criar peça com imagens disponíveis** solicita use_local_assets após falha elegível. Fundo neutro e assets locais passam pelo compositor e pelas regras existentes. Origem local/IA demonstrada na interface e no header do PNG. O estado operacional do job foi separado do conteúdo validado para preservar revisão, aprovação e PNG anterior em caso de falha; sucesso de uma nova composição exige revalidação.
- Cooldown para 429: pausa curta/Retry-After ou pausa conservadora de 24h para cota diária identificada. O controle e as ofertas são locais ao processo; detalhes em [fallback.md](../../docs/fallback.md). Bloqueios de segurança, erros de contrato/briefing/autenticação e HTTP 400 não oferecem fallback.
- Contratos estendidos com campos opcionais, sem novas rotas: Campaign.generation, RenderRequest.use_local_assets e origem/diagnóstico em VisualMetadata. Snapshots backend/frontend/raiz sincronizados; expectativas de contrato e classificação HTTP 400 atualizadas explicitamente, sem relaxar validações.
- Backend: **219 testes passaram**, incluindo 16 novos casos de fallback, consentimento, 429/503, cooldown, segurança, preservação de texto aprovado, PNG anterior, mock e disabled. Um aviso Starlette/HTTPX conhecido permaneceu. Comando: python -m pytest -q -p no:cacheprovider --tb=short.
- Frontend: **33 testes passaram, 1 teste HTTP opt-in ignorado**. Comando final: vitest run --pool=vmThreads --maxWorkers=1 --testTimeout=20000. Um worker da primeira execução não iniciou; os 8 testes visuais passaram isoladamente. Dois limites de espera inicial de UI foram ampliados de 1 para 5 segundos para a rodada completa, sem mudar as asserções. Os novos testes confirmam ausência de ação automática, preservação do briefing e ação correspondente à funcionalidade que falhou.
- TypeScript (tsc -b), lint (eslint .), build de produção (vite build) e git diff --check passaram. Node 24.22.1. Testes externos sempre simulados, com chaves fictícias e SQLite/armazenamento temporários; nenhuma chamada real de IA ou alteração de credenciais/.env/volumes/banco existente.
- Arquivos e limitações detalhados em [fallback.md](../../docs/fallback.md). Inspeção manual no navegador e disponibilidade dos provedores reais não foram verificadas. Nenhum git commit, merge ou push foi executado.

### Integração de texto, revisão e imagens — 2026-10-26

- Conflitos comparados entre HEAD e MERGE_HEAD. Serviços de consulta/validação/revisão unificados sem duplicação, preservando renderização e download de PNG. Cartões inteiros continuam navegáveis; briefing abre a mesma tela; rotas em português e inglês são aliases.
- `PieceDetail` mantém formulário RHF/Zod, confirmação explícita, validações por severidade, histórico completo e revisão por peça. `PieceVisual` extrai o painel do Alex e mantém plano Gemini, geração/novo fundo, recomposição, reutilização permitida, polling, erros, prévia e download. Conclusão da renderização atualiza detalhe/listas; ações editoriais ficam bloqueadas durante processamento.
- Mantidas as regras reais do servidor: aprovação exige estado validated e validação atual bem-sucedida, incluindo checagens visuais quando existe composição. Campanhas antigas/textuais e banner não recebem bloqueio adicional por ausência de imagem.
- Removidas duplicações de `queryKeys.campaign` e `ReviewRequest` introduzidas pelo merge automático. Proteção de 800 ms contra clique duplo preservada também quando a requisição responde imediatamente, após falha reproduzida pelo teste visual.
- Gemini: `generate()` e `generate_package()` preservam originalidade e prioridade de marca, excluindo somente `generation.templates` do contexto. Planejamento e metadados visuais do Alex permanecem. Dois testes adicionais verificam regras, produto, briefing, imutabilidade e mock no novo caminho combinado.
- A comparação do OpenAPI encontrou somente a descrição HTTP 422 dependente de Python (Unprocessable Entity/Content). Descrição explicitada em `backend/app/main.py` para preservar os snapshots existentes, sem alterar schemas, endpoints ou comportamento.
- Testes frontend das duas branches mantidos em `campaign-detail.test.tsx` e `campaign-visual.test.tsx`: **25 passaram; 1 teste HTTP opt-in ignorado**. Execução com Node 24.22.1, `vitest run --pool=threads --maxWorkers=1 --testTimeout=20000`. O pool de processos falhou ao iniciar dois workers neste ambiente; não foi necessário relaxar asserções.
- Dependências backend instaladas a partir de requirements.txt (Pillow e google-genai, com suas transitivas). Testes usam apenas chaves fictícias, mock, transportes simulados, SQLite e armazenamento temporários. Nenhuma operação de Docker/volume ou banco da demonstração foi executada.
- Verificações finais: **203 testes backend passaram**, com um aviso de depreciação Starlette/HTTPX já conhecido. TypeScript (`tsc -b`), lint (`eslint .`) e build de produção (`vite build`) passaram após a correção final de clique duplo. O teste de igualdade do OpenAPI passou sem mudança nos snapshots backend/frontend.
- Pendências: inspeção visual/manual no navegador e teste dos provedores reais ficam fora desta execução sem credenciais. `docs/openapi.json` da raiz ainda é histórico e não contém os contratos visuais; para integração, usar `backend/examples/openapi.json` ou `paguemenos-FRONT-END/docs/openapi.json`.
- Merge continua aberto. Nenhum git add, commit, push, abort ou reset foi executado; UU/AA no índice persistem intencionalmente até revisão humana.

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
