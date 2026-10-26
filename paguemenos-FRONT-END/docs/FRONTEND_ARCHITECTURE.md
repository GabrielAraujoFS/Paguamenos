# Arquitetura proposta do frontend

Estado: fundação, catálogo, briefing, listagem, detalhes de campanha, validação e revisão por peça implementados. Base documental: [API_CONTRACT.md](API_CONTRACT.md), [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md), [FRONTEND_IMPLEMENTATION_PLAN.md](FRONTEND_IMPLEMENTATION_PLAN.md) e [openapi.json](openapi.json). O contrato descreve o backend `0.1.0` do MVP local e sintético.

## Escopo documentado

O fluxo suportado é **catálogo → briefing → geração de campanha textual → validação de todas as peças → revisão humana por peça**. Cada campanha contém peças por canal (`feed`, `story`, `banner`); o estado pertence à peça (`draft`, `validated`, `approved`, `rejected`). O servidor persiste campanhas, validações e revisões. Catálogo e regras de marca são arquivos do servidor e podem mudar.

| Domínio | Entidades/contratos públicos | Operações disponíveis |
|---|---|---|
| Diagnóstico | `Health` | `GET /health` |
| Catálogo | `Product` | `GET /products`; `GET /products/{product_id}` |
| Geração e consulta | `Briefing`/`GenerateRequest`, `Campaign`, `Piece` | `POST /campaigns/generate` (201); `GET /campaigns/{campaign_id}` |
| Listagem | `CampaignPage`, `Campaign` | `GET /campaigns` com paginação, busca e filtro por estado de peça |
| Validação | `ValidationRun`, `ValidationResult` | `POST /campaigns/{campaign_id}/validate` (200 `Campaign`, sem body) |
| Revisão | `ReviewRequest`, `ReviewRecord`, `Piece` | `POST /pieces/{piece_id}/review` (200 `Piece`) |

São oito operações de domínio/saúde, sem prefixo `/api`. A listagem aceita `page`, `page_size`, `status`, `channel` e `search`; não aceita ordenação. IDs são strings opacas; preços são strings decimais; datas são ISO 8601 UTC. Sucessos vêm diretamente no JSON. Erros tratados usam `error.code`, `error.message` e `error.details`; `502` de geração existe no comportamento documentado, embora falte no OpenAPI. `404/409/422` são anunciados globalmente no OpenAPI, sem ramo efetivo em todas as rotas.

## Autenticação e permissões

Todas as operações atuais são públicas no backend. Não há usuários, login, sessão de usuário, JWT, refresh nem perfis. `reviewer_id` é texto enviado pelo cliente e não comprova identidade. Por isso, a arquitetura reserva um limite para autenticação/permissões futuras, mas **não** prevê tela de login, guarda de rota, token ou restrição por papel nesta versão. Mostrar/ocultar ações pelo estado da peça melhora a interface, mas a API decide a transição. Respostas 401/403 de infraestrutura externa não iniciam um fluxo de login inexistente.

## Stack e decisões técnicas

### Identidade visual

A interface usa a identidade Zyntra AI fornecida pelo projeto: azul-marinho (`#1d245c`) como base, azul (`#4e84e6`) e laranja (`#f39a1e`) como acentos, fundo azul-claro neutro e tipografia Geist Variable. As versões horizontal clara, horizontal escura e símbolo estão em `public/logos/`; o cabeçalho escuro usa a versão horizontal clara. Tokens de marca ficam em `src/index.css` e orientam os componentes, sem alterar contratos ou estados da API.

| Camada | Decisão proposta | Motivo |
|---|---|---|
| Base | React + TypeScript com `strict` + Vite | SPA tipada, compilação rápida e configuração pequena. Fixar versões estáveis compatíveis em lockfile quando a implementação começar. |
| Estilo e interface | Tailwind CSS + componentes shadcn/ui selecionados conforme uso | Layout responsivo e acessível sem trazer um kit inteiro. Componentes adicionados apenas quando necessários. |
| Navegação | React Router | URLs diretas para catálogo, produto e campanha por ID. |
| Dados remotos | TanStack Query + Axios centralizado | Cache por recurso, estados de requisição, mutações e erro HTTP normalizado. |
| Formulários | React Hook Form + Zod | Feedback imediato dos limites públicos de `Briefing` e `ReviewRequest`; servidor continua autoridade. |

Variável do frontend proposta: `VITE_API_BASE_URL`, padrão de desenvolvimento a definir na implementação para `http://127.0.0.1:8000`, sem sufixo `/api`. Não expor `GEMINI_API_KEY` ou qualquer segredo via variável `VITE_`. Para integração no navegador, a origem da UI deve coincidir com `CORS_ORIGINS` do backend: o padrão documentado aceita `http://localhost:5173`, não `http://127.0.0.1:5173`. A implantação remota depende de configuração/contrato posterior do backend.

## Organização planejada

```text
src/
  app/                 composição de providers, roteador e configuração
  layouts/             estrutura de navegação e conteúdo
  pages/               composição de telas e estados de rota
  components/ui/       componentes shadcn/ui usados no projeto
  components/shared/   feedback, diálogos e apresentação reutilizável
  features/
    catalog/            produto, seleção, hooks e apresentação
    campaigns/          briefing, geração, detalhe, validação e revisão
  api/                 cliente Axios, erros e serviços por recurso
  contracts/           DTOs de entrada/saída derivados da API
  auth/                limite reservado; sem implementação no MVP atual
  lib/                 formatação, chaves de consulta e utilitários
```

Esta árvore é um plano, não uma instrução para criar pastas vazias. Serviços HTTP não ficam nos componentes; hooks de TanStack Query coordenam leitura/mutação; páginas compõem recursos; componentes de interface não conhecem URLs da API. Manter um único tipo público para cada DTO, sem modelar tabelas SQLite internas como contratos do cliente.

## Rotas e componentes previstos

| Rota de interface proposta | Conteúdo | API usada |
|---|---|---|
| `/` ou `/campaigns/new` | Nova campanha; seleção de produto e briefing | `GET /products`, `POST /campaigns/generate` |
| `/products` | Catálogo | `GET /products` |
| `/products/:productId` | Produto, preço e oferta autorizada | `GET /products/{product_id}` |
| `/campaigns/:campaignId` | Briefing, peças, validação, revisão e históricos | `GET /campaigns/{campaign_id}`, `POST .../validate`, `POST /pieces/{piece_id}/review` |
| `/campanhas` | Listagem paginada, pesquisa por nome e filtro por estado de peça | `GET /campaigns` |
| `*` | Página de rota inexistente | nenhuma |

Um campo “Abrir campanha por ID” pode navegar para `/campaigns/:campaignId`. A listagem exibe estados por peça, pois a campanha não tem estado agregado, e `total` representa o resultado dos filtros atuais. Componentes previstos conforme uso: layout responsivo, seletor de produto, seleção de canais, campos com contador, cartão de peça, selo de estado, resultados por severidade, histórico de validações/revisões, diálogo de confirmação, estados de carregamento/vazio/erro e aviso de conexão. Não haverá editor de peça, publicação, administração ou dashboard operacional sem API correspondente.

## Fluxos e consistência

Integração de 2026-10-26: `/campaigns/:campaignId` e `/campanhas/:campaignId` são aliases da mesma tela. `PieceDetail` preserva conteúdo, validações, confirmação e histórico de revisão; `PieceVisual` reúne planejamento, geração de fundos, recomposição, reutilização autorizada, polling e `PiecePreview`. Os três serviços visuais correspondem às rotas reais `POST/GET /pieces/{id}/render` e `GET /pieces/{id}/image`. O estado visual vem de `RenderStatus`, sem acrescentar campos ao contrato `Piece`.

Operações editoriais ficam desabilitadas durante renderização ativa. Ao terminar o job, detalhe e listas são invalidados para obter o estado editorial corrente. A proteção contra clique duplo combina bloqueio durante requisição com janela de 800 ms para respostas imediatas. A aprovação segue o backend: campanhas textuais continuam aprováveis após validação; arte composta recebe também as checagens visuais. Não se exige imagem composta de todos os canais, pois essa restrição não existe no servidor.

1. Carregar produtos da API; enviar apenas campos aceitos em `GenerateRequest`. A geração retorna `Campaign` com uma peça `draft` por canal. Preservar formulário no `502` e oferecer nova tentativa explícita.
2. Abrir campanha por ID conhecido. `GET /campaigns/{id}` pode persistir a volta de `validated`/`approved` para `draft` se o fingerprint estiver desatualizado; substituir a visão pelo retorno atual. Histórico antigo não define estado presente.
3. Validar a campanha inteira sem body. Cada chamada cria um `ValidationRun` por peça; bloquear duplo envio e não repetir automaticamente. HTTP 200 com `success: false` é resultado de validação com falhas críticas, não erro HTTP. Severidade e códigos de regra são dados da API, sem quantidade ou ordem fixa.
4. Revisar uma peça por chamada. Mostrar aprovação quando `state === 'validated'` e a última validação teve sucesso; confirmar decisão e enviar `decision`, `reviewer_id` e `comment` opcional. O servidor ainda pode responder `409 APPROVAL_BLOCKED` por mudança recente. Rejeição é possível em qualquer estado, inclusive `approved`.
5. Após validação, gravar a resposta `Campaign` no cache da consulta por ID. Após revisão, substituir a peça retornada no cache correspondente e reconsultar a campanha quando precisar confirmar frescor. Em `409`, reconsultar a campanha antes de orientar revalidação. Mutações não têm retry automático.

Zod reproduz somente limites públicos de entrada: textos obrigatórios de 1–2000 após trim, 1–3 canais distintos, instruções adicionais até 4000; revisão com `reviewer_id` de 1–100 após trim e comentário até 2000. Não duplicar as regras de marca do servidor nem fixar limites editoriais de peça, pois não existe endpoint de configuração. Exibir mensagens do servidor para `422` por campo quando possível, e tratar falha de rede/500 sem presumir envelope JSON.

## Lacunas, riscos e dependências externas

| Impacto | Evidência documental | Efeito no frontend |
|---|---|---|
| Bloqueia acesso controlado | Sem autenticação, autorização ou perfis | Não é possível criar login real nem auditoria confiável do revisor. |
| Verificação visual pendente | Detalhes e ações testados por componentes e serviços HTTP; sem inspeção visual em navegador nesta etapa | Conferir encaixe e navegação em telas pequenas antes da apresentação. |
| Bloqueia edição e operação | Sem atualização/regeneração de peça, mídia, exportação, publicação, métricas ou CRUD de regras/produtos | Essas telas e ações aguardam novos contratos do backend. |
| Alto | Regras e catálogo mudam sem endpoint de configuração/eventos | Estado pode ser invalidado em consulta; validação do servidor é autoridade. |
| Alto | CORS documentado apenas para origens locais explícitas | Hospedagem remota exige decisão e configuração do backend. |
| Médio | Validação e revisão criam histórico; `GET` de campanha pode mudar estado | Evitar duplo envio, retry automático e suposição de idempotência. |
| Médio | Snapshot OpenAPI não descreve todos os erros de execução | Confirmar integração com backend vivo na próxima etapa. |

Não faltam os arquivos documentais essenciais para **planejar o MVP**: contrato, handoff, plano anterior e OpenAPI estão em `docs/`. Faltam, para recursos além dele, contratos de identidade/permissões, edição/regeneração, configuração de marca, publicação/mídia e implantação remota. Se a API viva divergir do snapshot, registrar a diferença antes de implementar comportamento dependente dela.
