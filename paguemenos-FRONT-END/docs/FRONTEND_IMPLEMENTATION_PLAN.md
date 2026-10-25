# Plano de implementação do frontend

Objetivo: implementar o fluxo **local e sintético** suportado pela API FastAPI `0.1.0`, sem depender de acesso ao código do backend. Contratos, exemplos e erros estão em [API_CONTRACT.md](API_CONTRACT.md); contexto e execução em [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md). Este plano recomenda uma organização de trabalho, não impõe framework.

> Atualização de 2026-10-24: `GET /campaigns` passou a existir no OpenAPI vivo, com paginação, busca e filtros. A listagem foi implementada em `/campanhas`; as referências abaixo à ausência desse endpoint descrevem o contrato anterior.

## Prioridades e dependências

| Etapa | Prioridade | Entrega | Dependência | Critério de aceitação |
|---|---|---|---|---|
| 0. Conexão e contratos | P0 | URL-base configurável, tipos `Product`/`Briefing`/`Campaign`/`Piece`/erros, cliente JSON centralizado | backend local e CORS corretos | `GET /health` e `GET /products` funcionam do navegador; erro estruturado aparece com `code` e `message`; nenhum segredo no bundle. |
| 1. Catálogo e briefing | P0 | Seleção de produto; formulário com 4 textos, 1–3 canais distintos, instruções opcionais | etapa 0 | Produtos vêm da API; ID correto é enviado; entradas vazias/duplicadas são bloqueadas no formulário; servidor ainda é autoridade para 422. |
| 2. Geração e detalhes | P0 | Gerar campanha; renderizar peças por canal; rota/tela de detalhes por ID conhecido | etapa 1 | `POST /campaigns/generate` retorna 201; cada canal pedido gera uma peça `draft`; campanha pode ser reaberta por `GET /campaigns/{id}`; loading impede reenvio acidental; 502 preserva briefing e permite retry explícito. |
| 3. Validação | P0 | Botão de validar campanha, resultados por peça, histórico | etapa 2 | `POST /campaigns/{id}/validate` sem body atualiza todas as peças; renderiza última execução e histórico; `success: false` com HTTP 200 é mostrado como falha de regra; severidades `critical`/`warning`/`info` são distintas. |
| 4. Revisão humana | P0 | Aprovar/rejeitar uma peça, `reviewer_id` e comentário, confirmação, histórico | etapa 3 | Aprovação só é oferecida quando estado atual `validated` e última validação bem-sucedida; 409 recarrega campanha e informa bloqueio; rejeição funciona em qualquer estado; resposta `Piece` atualiza peça correta. |
| 5. Robustez e acessibilidade | P1 | Estados vazios, 404, erro de rede, navegação, responsividade, teclado | etapas 0–4 | IDs inválidos mostram 404; carregamentos e falhas têm feedback; controles são rotulados e operáveis por teclado; a tela não afirma aprovação com base apenas no histórico. |
| 6. Conveniências locais | P2 | Histórico local de IDs e diagnóstico discreto | etapas 2–5 | IDs locais abrem via GET; é indicado que o histórico pertence ao navegador/dispositivo e pode ficar obsoleto; `/health` não é interpretado como prova de acesso ao Gemini. |

P0 é suficiente para o fluxo funcional demonstrável. P2 não substitui a ausência de listagem de campanhas na API. Não planeje como entrega funcional telas de login, administração, edição, publicação ou dashboard analítico sem mudanças no backend.

## Matriz de rastreabilidade: módulo → tela → ação → endpoint → permissão

| Módulo | Tela/componente | Ações disponíveis | Endpoint(s) | Permissão efetiva | Situação |
|---|---|---|---|---|---|
| Infraestrutura | Indicador de conexão | Consultar saúde/provedor | `GET /health` | nenhuma | suportada |
| Catálogo | Seleção de produto | Listar e escolher | `GET /products` | nenhuma | suportada |
| Catálogo | Detalhe do produto | Consultar produto/preço/oferta | `GET /products/{product_id}` | nenhuma | suportada |
| Campanha | Novo briefing | Preencher e gerar | `GET /products`, `POST /campaigns/generate` | nenhuma | suportada |
| Campanha | Detalhe por ID | Abrir, ver briefing e peças | `GET /campaigns/{campaign_id}` | nenhuma | suportada se ID conhecido |
| Validação | Painel por peça dentro do detalhe | Validar campanha, ler resultados e histórico | `POST /campaigns/{campaign_id}/validate`, `GET /campaigns/{campaign_id}` | nenhuma | suportada; operação valida todas as peças |
| Revisão | Ações e histórico da peça | Aprovar/rejeitar manualmente | `POST /pieces/{piece_id}/review`, `GET /campaigns/{campaign_id}` | nenhuma; `reviewer_id` autodeclarado | suportada; uma peça por chamada |
| Campanhas | Lista global/pesquisa | Descobrir campanhas anteriores | nenhum | indefinida | **depende do backend** |
| Peça | Editor/regeneração | Alterar título, legenda, CTA, imagens | nenhum | indefinida | **depende do backend** |
| Administração | Login, usuários, marca, regras | Gerir acesso/configuração | nenhum | indefinida | **depende do backend** |
| Operação | Dashboard, exportar, publicar | Agregar/baixar/publicar | nenhum | indefinida | **depende do backend** |

## Telas e formulários

### Nova campanha

Campos: `campaign_name`, `product_id` selecionado de `/products`, `objective`, `target_audience`, `channels` com `feed`/`story`/`banner` sem repetição e `additional_instructions` opcional. O cliente pode contar 1–2000 caracteres para os quatro textos obrigatórios e até 4000 nas instruções. O backend faz trim e rejeita campos extras; não envie preço, oferta, disclaimer ou conteúdo da peça. Renderize produto com nome, descrição, categoria, preço string e oferta autorizada. O preço deve ser formatado para leitura com cuidado, mantendo a string original para qualquer comparação ou armazenamento.

### Detalhe da campanha

Use `campaign.id` para reabrir por GET. Mostre briefing e uma peça por canal retornado, na ordem recebida. Cada peça mostra `title`, `subtitle`, `cta`, `disclaimer`, produto, preço, oferta, estado atual, validações e revisões. Não há estado oficial agregado; se desejar um resumo visual, rotule-o como cálculo da interface. Não há GET de peça isolada. A consulta pode alterar estado de peças desatualizadas; substitua o estado da tela pela resposta mais recente.

### Validação e revisão

Validação não recebe body. Ao clicar, informe que uma execução histórica será acrescentada a cada peça. Mostre `success` e resultados da última execução, com filtros **locais de apresentação** por severidade/status se úteis; não existe filtro de API. `rule_code` e `field` são texto aberto. `field` às vezes contém campos separados por vírgulas, portanto erros sem campo editável vão ao painel geral. Distinga falhas críticas de avisos e informação. O botão de aprovação deve pedir confirmação e campos `reviewer_id` (1–100 após trim) e `comment` opcional (até 2000). `reviewer_id` é identificador declarado, não usuário autenticado. A ação 409 pede atualização e revalidação conforme o estado recebido. Rejeição pode ocorrer em qualquer estado e também exige confirmação por criar histórico permanente.

## Organização sugerida, independente de framework

```text
src/
  api/             cliente HTTP, URL-base, erros e serviços de produto/campanha/revisão
  contracts/       tipos TypeScript derivados da API, sem modelos de banco
  features/        fluxo de briefing, catálogo, campanha, validação e revisão
  components/      campos, cartão de peça, badge de estado, lista de resultados, diálogo
  pages/           nova campanha, catálogo, detalhe por ID e 404
  state/           estado de requisição/cache por campanha e IDs conhecidos localmente
```

Responsabilidades **exigidas pela integração**: JSON correto, `Content-Type` nos POST com body, IDs e preços preservados, transições decididas pelo servidor, tratamento de 404/409/422/502, origem CORS autorizada. Responsabilidades **recomendadas**: cache por ID, invalidação após mutações, validação visual dos formulários, feedback de loading, normalizador de erros, componentes compartilhados e testes de fluxo. Nenhuma biblioteca específica de roteamento, estado ou formulário é exigida.

## Cenários de aceitação integrados

1. Com mock e catálogo inicial, selecionar `syn-001`, enviar `channels: ["feed", "story"]`, receber 201 com duas peças `draft`, preço como string e históricos vazios.
2. Tentar aprovar antes de validar recebe 409 `APPROVAL_BLOCKED`; a tela conserva a peça e orienta a validar.
3. Validar campanha retorna 200 com um `ValidationRun` por peça. Se `success: true`, estado `validated`; avisos não impedem sucesso.
4. Aprovar uma peça validada retorna `Piece` com `state: "approved"` e novo registro em `reviews`; a outra peça mantém seu próprio estado.
5. Rejeitar peça existente retorna `rejected` mesmo se antes era `draft`/`approved`; após revalidação bem-sucedida ela volta a `validated`.
6. Reabrir campanha por ID mostra histórico persistido; após mudança do catálogo/regras no servidor, estado antigo pode voltar a `draft` e a tela oferece revalidação.
7. Produto/campanha/peça inexistente mostra 404 específico; briefing inválido mostra 422 e campos; falha prevista de Gemini mostra 502 e opção de nova tentativa manual.
8. Origem frontend configurada funciona no navegador. Frontend em origem distinta da lista CORS falha no preflight; configuração é ajustada no backend, sem contorno de segurança no cliente.

## Itens que exigem definição ou backend novo

| Impacto | Necessidade | Dependência concreta |
|---|---|---|
| Bloqueante para acesso controlado | Login, logout, papéis, sessão, recuperação | Modelo de usuários e endpoints/middleware de autenticação/autorização; atualmente todas as rotas são públicas. |
| Bloqueante para descoberta de campanhas | Lista/pesquisa/filtros/paginação de campanhas | Endpoint de listagem e contrato de paginação; somente GET por ID existe. |
| Bloqueante para correção de conteúdo | Editar peça/briefing, regenerar variante | Endpoint de atualização/regeneração e regras de invalidação; atualmente só se pode criar campanha nova. |
| Bloqueante para visual/mídia | Upload/download, imagem, exportação/publicação | Contratos e armazenamento ausentes. |
| Bloqueante para administração | Regras/cores/produtos pela UI | Endpoints de configuração/CRUD ausentes; arquivos JSON são internos. |
| Alto para implantação remota | CORS e autenticação de produção | CORS atual só admite origens locais explícitas; backend é MVP local. |
| Médio para alinhamento visual | Regras configuráveis sem endpoint | Frontend pode exibir resultados recebidos, mas não conhecer antecipadamente limites/expressões ativos. |

Não implemente esses itens como se fossem suportados. Caso sejam desejados, documente uma proposta de contrato separada e aguarde implementação do backend.

## Revisão de conclusão do frontend

- Todos os botões operacionais têm rota correspondente na matriz.
- Todos os formulários enviam apenas campos aceitos; formatos de data/preço são preservados.
- Nenhum fluxo de login/refresh/perfil é simulado como segurança real.
- Há feedback para espera, vazio, 404, 409, 422, 502 e falha de rede.
- Estado atual da peça vem da última resposta da API, não de revisão histórica.
- Testes do frontend cobrem os oito cenários de aceitação acima com mock da API ou backend local.

