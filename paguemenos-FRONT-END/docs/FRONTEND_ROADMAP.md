# Roadmap do frontend

Estado: etapas 0 a 4, mais listagem de campanhas, implementadas; a verificação visual no navegador com backend ativo continua pendente. Os serviços de detalhe, validação e revisão foram exercitados contra FastAPI temporário com SQLite descartável e provedor mock. Referências: [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md), [API_CONTRACT.md](API_CONTRACT.md) e [FRONTEND_IMPLEMENTATION_PLAN.md](FRONTEND_IMPLEMENTATION_PLAN.md).

| Etapa | Prioridade | Entrega planejada | Critério de conclusão |
|---|---|---|---|
| 0. Fundação e conexão | P0 | Projeto React/TypeScript/Vite, dependências estáveis travadas em lockfile, Tailwind, shadcn/ui conforme uso, roteador, Axios, TanStack Query, configuração da URL e tipos da API | Build e checagem de tipos passam; `GET /health` e `/products` funcionam no navegador com CORS configurado; erros têm tratamento central. |
| 1. Catálogo e briefing | P0 | Catálogo e detalhe do produto; formulário React Hook Form/Zod com produto da API, quatro textos, 1–3 canais e instruções opcionais; envio a `POST /campaigns/generate` com confirmação mínima | Envia somente campos documentados, preserva preço string, bloqueia entradas inválidas conhecidas e exibe `422` por campo. |
| Listagem de campanhas | P0 | `/campanhas` com paginação, pesquisa, filtro por estado de peça e atualização manual | Consome `GET /campaigns` real; usa `total` e páginas do servidor, sem inventar estado agregado. |
| 2. Geração e consulta | P0 | Completar a experiência de geração com navegação para `/campaigns/:id`, detalhe completo das peças e abertura por ID conhecido | Resposta 201 exibe uma peça `draft` por canal; reload por ID usa GET; `502` preserva briefing e oferece retry manual; sem envio duplicado. |
| 3. Validação | P0 | Ação para campanha inteira, última execução e histórico por peça, resultados por severidade | POST sem body atualiza cache com `Campaign`; `success: false` em 200 é mostrado corretamente; segunda execução só ocorre por ação explícita. |
| 4. Revisão | P0 | Aprovar/rejeitar peça com identificador autodeclarado, comentário, confirmação e histórico | Aprovação segue estado visível, servidor decide; `409` reconsulta; resposta `Piece` atualiza a peça correta; rejeição funciona em qualquer estado permitido. |
| 5. Qualidade de uso | P1 | Responsividade, acessibilidade, loading/vazio/404/falha de rede, navegação por teclado | Fluxo principal funciona em telas pequenas e grandes, com controles rotulados, foco adequado e feedback de erro. |
| 6. Conveniência local opcional | P2 | Histórico local de IDs, se útil, e status discreto do backend | Escopo local é explícito; IDs são revalidados por GET; `/health` não é apresentado como prova de conectividade do gerador. |

## Sequência de entrega e testes

- Após a etapa 0, conferir o snapshot `docs/openapi.json` com `/openapi.json` do servidor disponível e registrar divergências; não corrigir o backend neste repositório.
- Nas etapas 1–4, testar os contratos de requisição/resposta e os estados principais com fixtures fiéis à API; fazer ao menos um fluxo real com backend em modo mock quando estiver acessível.
- Cobrir no fluxo real ou de integração: produto inexistente (404), briefing inválido (422), geração indisponível (502 simulado quando necessário), campanha inexistente (404), validação com falha crítica em 200, aprovação bloqueada (409), rejeição e revalidação. Não depender de dados fixos do catálogo além dos retornados pela API.
- Ao fechar cada etapa, atualizar [FRONTEND_PROGRESS.md](FRONTEND_PROGRESS.md) com evidência dos comandos/testes e pendências.

## Dependências fora do escopo atual

Login e perfis, edição/regeneração, configuração de marca e catálogo por UI, mídia/publicação e dashboard exigem novos endpoints e regras do backend. Listagem, detalhe por ID, validação e revisão estão implementados. Hospedagem fora das origens locais exige configuração CORS e decisão de segurança do backend.
