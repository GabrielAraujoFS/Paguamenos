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
- [ ] Etapa 2 — Geração e consulta por ID.
- [ ] Etapa 3 — Validação da campanha.
- [ ] Etapa 4 — Revisão por peça.
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
- [ ] Testes de atualização de cache — previstos para validação/revisão, que alteram campanha.
- [ ] Teste responsivo e de acessibilidade — interface ainda não implementada.

## Pendências e bloqueios documentados

- [x] Confirmar acesso HTTP temporário ao backend real em `127.0.0.1:8000` e CORS para `http://localhost:5173`; falta validar a interface no navegador com ambos os servidores ativos.
- [x] Registrar divergência entre documentação anterior e API viva antes de adaptar contratos; snapshot OpenAPI atualizado.
- [ ] Obter contratos de autenticação/perfis se o produto exigir acesso controlado; hoje as sete operações são públicas.
- [x] Confirmar API de listagem/pesquisa: `GET /campaigns` disponível no backend local.
- [ ] Obter contratos de edição/regeneração, mídia/publicação, regras/produtos administráveis e métricas se essas funções forem requisitadas.
- [ ] Definir hospedagem e CORS de produção com o backend; a configuração documentada é local.

## Registro de alterações

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
