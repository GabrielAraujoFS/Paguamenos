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
Use strings decimais para preservar centavos. No MVP não há paginação, edição,
listagem de campanhas ou status agregado da campanha.

## Decisões de Emily

- Regras oficiais de marca, tom de voz, mensagens e avisos obrigatórios.
- Limites de caracteres definitivos por campo/canal e severidade das regras.
- Catálogo e ofertas autorizados para a demonstração final.
- Critérios de aprovação/rejeição e identificação dos revisores na apresentação.
- Provedor/modelo de IA, uso autorizado de dados e comportamento esperado das variações,
  incluindo como objetivo, público e instruções adicionais influenciam o texto.

Até essas decisões, toda regra e todo dado comercial permanecem sintéticos.
Não se atribuem essas regras à Pague Menos. A integração React pode avançar
com os contratos atuais para a entrega de 21/10/2026; o hackathon é em 26/10/2026.
