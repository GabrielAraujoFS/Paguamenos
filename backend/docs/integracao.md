# Contratos para Alexsandro

Fonte de verdade executável: GET /openapi.json; interface interativa: GET /docs.
O diretório examples contém corpos completos gerados pela própria aplicação,
incluindo IDs ilustrativos. IDs mudam a cada execução; sempre use os da resposta.

## Compartilhar

1. Briefing: campaign_name, product_id, objective, target_audience, channels,
   additional_instructions opcional/null. Textos obrigatórios não aceitam vazio.
2. Channel: feed, story, banner, sem duplicatas; de um a três canais.
3. Product: id, name, description, category, price (string decimal), authorized_offer.
4. Campaign: id, created_at em UTC, briefing e pieces.
5. Piece: id, campaign_id, channel, title, subtitle, cta, disclaimer, product_id,
   product_name, price (string decimal), authorized_offer, state, validations, reviews.
6. ValidationRun: id, created_at, fingerprint, success, results.
   Cada resultado contém rule_code, severity, message, field, passed.
7. Revisão: enviar decision (approved/rejected), reviewer_id simulado, comment opcional.
   Retorna Piece completa. Cada registro contém id, data, decisão, revisor,
   comentário e fingerprint. O histórico não equivale a aprovação do conteúdo atual.
8. Estados: draft → validated → approved; rejected por decisão humana.
   Falha/desatualização volta a draft; rejeitada exige nova validação para aprovar.
9. Erros: error.code, error.message, error.details. Tratar 404, 409 e 422.
10. Origens CORS explicitamente configuradas; padrão http://localhost:5173.
    POST JSON com Content-Type: application/json; nenhum token no MVP.

## Histórico paginado de campanhas

`GET /campaigns` retorna `CampaignPage`. No backend esta é a rota REST completa;
no ambiente Compose, o Nginx aceita `GET /api/campaigns` e remove `/api/` ao
encaminhar a chamada. Assim, o frontend pode usar `GET /api/campaigns` na mesma
origem em que a interface foi carregada (ou `http://127.0.0.1:8000/campaigns`
quando chamar o backend diretamente). A rota também está no Swagger (`/docs`) e
no OpenAPI (`/openapi.json`).

```ts
interface CampaignPage {
  items: Campaign[]; total: number; page: number;
  page_size: number; total_pages: number;
}
```

Cada `Campaign` de `items` tem a mesma estrutura de `GET /campaigns/{campaign_id}`:
`id` UUID textual, `created_at` UTC ISO 8601, `briefing` completo e `pieces`
com conteúdo, estado, validações e revisões. Não existe status agregado de campanha.
O exemplo completo está em `../examples/responses.json`, chave `list_campaigns`.

Parâmetros opcionais: `page` inteiro >= 1 (padrão 1), `page_size` inteiro entre
1 e 100 (padrão 20), `status` em `draft|validated|approved|rejected`, `channel`
em `feed|story|banner` e `search` texto de ao menos um caractere. `status`
corresponde ao estado de **qualquer peça**; `channel` corresponde ao canal de
qualquer peça, possivelmente outra peça da mesma campanha. `search` procura
substring sem diferenciar caixa em nome, objetivo e público-alvo do briefing;
espaços nas bordas são removidos e texto só de espaços desativa a busca. As
campanhas são ordenadas por data de criação decrescente e ID decrescente como
desempate. `total` considera os filtros; não há duplicatas. Banco vazio gera
`items: []`, `total: 0`, `total_pages: 0`. Página além do fim gera `items: []`
com `total` e `total_pages` preservados. Entradas inválidas retornam 422 no envelope
`INVALID_REQUEST`; erros inesperados de banco não têm envelope garantido.

Para percorrer todo o histórico, faça requisições de `page=1` até
`page=total_pages`, mantendo `page_size` e filtros iguais. Use
`GET /campaigns/{campaign_id}` com um ID obtido da lista para abrir os detalhes;
ID inexistente retorna 404 `CAMPAIGN_NOT_FOUND`. A listagem é somente leitura e
não recalcula estado; o detalhe existente pode invalidar um estado antigo se
produto/regras mudaram. Nenhum endpoint gera conteúdo durante essas consultas.

Exemplo:

```http
GET /api/campaigns?page=1&page_size=20&status=approved&channel=feed
Accept: application/json
```

`Accept: application/json` é recomendado; não há body, token, cookie ou
`Authorization` exigido. A rota responde 200 com `CampaignPage`; parâmetros
inválidos respondem 422 no envelope `error` comum. A lista vazia retorna 200
com `items: []`, `total: 0`, `page: 1`, `page_size: 20` e `total_pages: 0`.
Os itens usam o schema público `Campaign` (`id`, `created_at`, `briefing` e
`pieces`); status é por peça e não há status agregado nem contador calculado.
Uma resposta completa e atualizada por execução está em
`../examples/responses.json`, chave `list_campaigns`.

Em desenvolvimento direto, a origem padrão permitida por CORS é
`http://localhost:5173`. As origens locais são explícitas via `CORS_ORIGINS`;
não se habilitam origens arbitrárias. Pelo proxy Nginx `/api`, a chamada é
same-origin e não depende de CORS.

## Fluxo React

GET /products → selecionar produto → POST /campaigns/generate →
mostrar pieces → POST /campaigns/{id}/validate → mostrar results por peça →
aguardar ação humana → POST /pieces/{id}/review → atualizar pelo retorno
ou consultar GET /campaigns/{id}. Não aprovar automaticamente.

Exemplo de geração (a partir do frontend local):

```javascript
const response = await fetch("http://127.0.0.1:8000/campaigns/generate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    campaign_name: "Cuidados de demonstração",
    product_id: "syn-001",
    objective: "Apresentar produto fictício",
    target_audience: "Público adulto fictício",
    channels: ["feed", "story", "banner"]
  })
});
const body = await response.json();
if (!response.ok) throw new Error(body.error.message);
// body.id e body.pieces contêm os identificadores para os próximos passos.
```

Preços são dados autorizados de exibição, não saída da IA.
Use strings decimais para preservar centavos. Há paginação na listagem de
campanhas; ainda não há edição nem status agregado da campanha.

## Atualização configurável: o que muda para o frontend

Os contratos dos sete endpoints anteriores permanecem iguais; a listagem é o
oitavo endpoint. O teste de contrato compara o OpenAPI atual ao snapshot exportado.
Não há endpoint
de marca ou campos novos no briefing. Uma peça por canal solicitado e um único
`target_audience` por campanha continuam sendo o comportamento vigente.

O conteúdo do mock pode mudar com a configuração, assim como o número de resultados
de validação. Não dependa de textos fixos, da posição das regras na lista nem de
uma lista fechada de `rule_code`. Novos códigos: `REQUIRED_EXPRESSION`,
`FORBIDDEN_EXPRESSION`, `TEXT_PRICE_MATCH`, `TEXT_OFFER_MATCH`.

- Exiba mensagens e diferencie `critical`, `warning` e `info`.
- `passed: false` com `warning`/`info` não bloqueia aprovação. Não use
  `results.every(r => r.passed)` como critério para liberar a revisão.
- Considere o estado atual e `validations[validations.length - 1].success`.
  A aprovação é sempre explícita e o servidor decide, retornando 409 se bloqueada.
- `field` é texto: normalmente contém o nome do campo; em `REQUIRED_EXPRESSION`
  pode listar campos candidatos separados por vírgula. Se não houver um campo
  editável correspondente, mostre a mensagem na área geral de validação.
- Mudanças no perfil/regras, inclusive a atualização desta versão, podem tornar
  antigas validações/aprovações inaplicáveis. Atualize a campanha por GET e ofereça
  revalidação; preserve a exibição do histórico como registro de decisões passadas.
- Saída inválida de um futuro provedor também retorna erro estruturado 502,
  código `GENERATION_CONTRACT_ERROR`; não indica falha de validação de marca.

Consulte [configuração e limitações](configuracao.md) e os
[exemplos completos de alerta e bloqueio](../examples/configurable_validation.json).
As configurações locais do exemplo não são enviadas pelo React.
`generation_provider: mock` identifica geração simulada; `gemini` identifica o
adaptador real configurado (não comprova conectividade). `custom` identifica
outras implementações injetadas. Não dependa de uma lista fechada com mock/custom.

## Integração Gemini opcional

Os contratos de geração anteriores permanecem iguais. Geração pode demorar: mantenha
indicador de espera e evite envios duplicados. `subtitle` é a legenda; permanece
uma peça por canal. Todos os erros previstos da integração usam 502 no envelope
existente, incluindo GENERATION_AUTH_ERROR, GENERATION_RATE_LIMIT,
GENERATION_TIMEOUT, GENERATION_UNAVAILABLE e GENERATION_CONTRACT_ERROR.
Mostre error.message e permita nova tentativa explícita; não há fallback.
A chave é exclusiva do backend. Fluxo continua gerar → validar → revisar.
Consulte [configuração e limitações](geracao-ia.md).

## Decisões de Emily

- Regras oficiais de marca, tom de voz, mensagens e avisos obrigatórios.
- Limites de caracteres definitivos por campo/canal e severidade das regras.
- Catálogo e ofertas autorizados para a demonstração final.
- Critérios de aprovação/rejeição e identificação dos revisores na apresentação.
- Provedor/modelo de IA, uso autorizado de dados e comportamento esperado das variações,
  incluindo como objetivo, público e instruções adicionais influenciam o texto.

Até essas decisões, toda regra e todo dado comercial permanecem sintéticos.
Não se atribuem essas regras a nenhuma marca real. A integração React pode avançar
com os contratos atuais para a entrega de 21/10/2026; o hackathon é em 26/10/2026.
