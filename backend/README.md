# Creative Factory + Brand Guardian — backend MVP

Python 3.13, FastAPI, Pydantic, SQLite e SQLAlchemy. Fluxo local:
briefing → geração textual (mock ou Gemini) → validação objetiva → revisão humana.
Dados, ofertas e regras são sintéticos e não representam regras oficiais de marcas reais.
Gemini é opcional; mock permanece padrão. Sem frontend, imagens, autenticação complexa ou publicação automática.
Consulte [configuração de IA e nível gratuito](docs/geracao-ia.md).
Mantenha o repositório privado. Nenhum commit ou publicação é necessário para executar.

## Instalação e execução

No PowerShell, na raiz do projeto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
$env:DATABASE_URL = 'sqlite:///./creative_factory.db'
$env:CORS_ORIGINS = 'http://localhost:5173'
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

As variáveis são opcionais e os valores acima são os padrões. O banco e as tabelas
são criados na inicialização. `.env.example` é referência; não há carregamento
automático de `.env`. Para múltiplas origens locais, separe por vírgulas;
`http://127.0.0.1:5173` precisa ser configurada separadamente.
CORS permite GET e POST, sem cookies. O MVP destina-se à execução local,
com identificadores de revisão simulados e sem autenticação.

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json).

## Estrutura

- `app/api/`: rotas, dependência transacional e revisão.
- `app/schemas/`: contratos Pydantic e enums.
- `app/models/` e `app/database.py`: persistência e conexões SQLite.
- `app/services/generation.py`: interface e gerador mock determinístico.
- `app/services/validation.py`: verificações objetivas.
- `app/services/workflow.py`: estados, invalidação e respostas.
- `app/data/products.json`: catálogo sintético de cinco produtos.
- `app/data/brand_rules.json`: regras sintéticas configuráveis.
- `app/schemas/configuration.py`: validação da configuração interna, sem novos campos na API.
- `tests/`: banco temporário independente por teste.
- `examples/`: requisições e respostas reais do mock, incluindo erros.
- `docs/integracao.md`: contrato para Alexsandro e decisões de Emily.

## Endpoints

| Método | Caminho | Sucesso | Retorno |
|---|---|---|---|
| GET | /health | 200 | Status e provedor |
| GET | /products | 200 | Lista de produtos |
| GET | /products/{product_id} | 200 | Produto |
| POST | /campaigns/generate | 201 | Campanha completa com peças draft |
| GET | /campaigns | 200 | Página de campanhas completas, incluindo peças e históricos |
| GET | /campaigns/{campaign_id} | 200 | Campanha, validações e revisões |
| POST | /campaigns/{campaign_id}/validate | 200 | Campanha com nova validação por peça |
| POST | /pieces/{piece_id}/review | 200 | Peça com decisão e histórico |

Não há corpo na validação. O estado pertence à peça, e não à campanha.
404 indica recurso inexistente; 422 indica entrada inválida; 409 bloqueia aprovação;
502 indica incompatibilidade dos canais devolvidos pelo gerador.
Erros usam `{"error":{"code":"...","message":"...","details":[]}}`.
Os tipos e campos completos estão em OpenAPI.

### Histórico de campanhas

`GET /campaigns?page=1&page_size=20` lê o SQLite e retorna
`{items: Campaign[], total: int, page: int, page_size: int, total_pages: int}`.
`page` começa em 1; `page_size` vai de 1 a 100 (padrão 20). Os itens são campanhas
completas, com briefing, peças, validações e decisões, ordenadas por `created_at`
decrescente e, em empate, por `id` decrescente. Uma página além do fim retorna
`items: []`, mantendo `total` e `total_pages`; banco vazio retorna `total_pages: 0`.
Percorra `page=1` até `page=total_pages` para recuperar todo o histórico. Não há
limite global de campanhas recuperáveis.

Filtros opcionais: `status` (`draft`, `validated`, `approved`, `rejected`) seleciona
campanhas com **alguma peça** nesse estado; `channel` (`feed`, `story`, `banner`)
seleciona campanhas com alguma peça nesse canal; `search` faz busca de substring
sem diferenciar maiúsculas/minúsculas no nome, objetivo ou público-alvo do briefing.
Filtros de estado e canal são independentes: podem corresponder a peças diferentes
da mesma campanha. Espaços nas bordas de `search` são ignorados; valor só de espaços
equivale a ausência de busca. O total é calculado após os filtros. Parâmetros
inválidos retornam 422 `INVALID_REQUEST`. Sem filtros, todos os estados entram.
A listagem não recalcula validações nem altera estados; para consultar e atualizar
o estado corrente de uma campanha específica, use `GET /campaigns/{campaign_id}`.

Exemplo abreviado (cada item real inclui a campanha inteira):

```json
{"items":[{"id":"55e27e3b-0e89-4347-b716-63b85cf7cff4","created_at":"2026-10-20T04:14:41.055582Z","briefing":{"campaign_name":"Campanha Aurora","product_id":"syn-001","objective":"Divulgar produto sintético","target_audience":"Adultos interessados em higiene pessoal","channels":["feed","story","banner"],"additional_instructions":"Demonstração de hackathon"},"pieces":[{"id":"dc6e6903-ea68-478a-9870-daf816f74e21","campaign_id":"55e27e3b-0e89-4347-b716-63b85cf7cff4","channel":"feed","title":"Marca de demonstração: conheça Sabonete Brisa","subtitle":"Sabonete corporal fictício de uso diário. Cuidado com informação clara.","cta":"Conheça o produto","disclaimer":"Campanha fictícia. Dados sintéticos.","product_id":"syn-001","product_name":"Sabonete Brisa","price":"8.90","authorized_offer":"Preço sintético de demonstração, sem desconto adicional.","state":"draft","validations":[],"reviews":[]}]}],"total":1,"page":1,"page_size":20,"total_pages":1}
```

O exemplo acima mostra só uma das peças para caber nesta seção; o exemplo completo
da listagem está em `examples/responses.json`. IDs e datas desse arquivo são
ilustrativos e vêm de respostas do mock.

O caminho do banco **local**, ao executar a partir de `backend`, é
`backend/creative_factory.db` (`sqlite:///./creative_factory.db`). No Compose é
`/data/creative_factory.db` dentro do contêiner, preservado no volume nomeado
`backend_data` (`sqlite:////data/creative_factory.db`). São bancos diferentes;
não há migração ou cópia automática. Para identificar o banco ativo, confira
`DATABASE_URL` no ambiente do processo/contêiner, sem expor outras variáveis.

## Como testar no Swagger

1. Inicie a API e abra `http://127.0.0.1:8000/docs`.
2. Expanda `GET /health`, clique **Try it out → Execute**. Espere 200 e status ok.
3. Execute `GET /products`, depois `GET /products/{product_id}` com `syn-001`.
4. Em `POST /campaigns/generate`, clique **Try it out**, cole o JSON abaixo e execute:
   ```json
   {
     "campaign_name": "Cuidados de demonstração",
     "product_id": "syn-001",
     "objective": "Apresentar produto fictício",
     "target_audience": "Público adulto fictício",
     "channels": ["feed", "story", "banner"],
     "additional_instructions": null
   }
   ```
5. Na resposta 201, copie `id` da campanha e `pieces[0].id`.
6. Opcional: tente aprovar antes de validar; deve retornar 409, sem registrar aprovação.
7. Em `POST /campaigns/{campaign_id}/validate`, informe o ID da campanha e execute.
   Espere 200, peças em `validated` e `validations[-1].success = true`.
8. Em `POST /pieces/{piece_id}/review`, informe o ID da primeira peça e este corpo:
   ```json
   {"decision":"approved","reviewer_id":"revisor-demo","comment":"Revisado manualmente."}
   ```
   Espere 200, `state = approved` e uma revisão com ID, data UTC e revisor.
9. Consulte `GET /campaigns/{campaign_id}` para verificar o histórico persistido.
10. Para rejeitar outra peça, use `{"decision":"rejected","reviewer_id":"revisor-demo"}`.
    A rejeição é permitida em qualquer estado. Aprovar uma rejeitada exige nova validação.
11. Execute `GET /campaigns?page=1&page_size=20` para ver o histórico paginado.

## Estados e validação

- `draft`: peça recém-gerada, com falha crítica ou validação desatualizada.
- `validated`: última validação bem-sucedida e correspondente ao conteúdo atual.
- `approved`: decisão humana explícita após validação atual bem-sucedida.
- `rejected`: rejeição humana explícita, preservada no histórico.

A validação registra resultados com `rule_code`, `severity`, `message`,
`field` e `passed`, além de data, fingerprint e sucesso global.
Produto existente, preço, nome, oferta autorizada, campos obrigatórios e canal
continuam críticos. Expressões obrigatórias/proibidas e regras editoriais podem
produzir alertas configurados. O Guardian também verifica preços e condições no
texto dentro dos formatos suportados. Falhas `warning`/`info` não impedem `success: true`.
Os limites são configuráveis por canal no JSON. Todos os resultados, inclusive os
aprovados, ficam registrados. Revalidar cria um novo registro; uma aprovação atual
é preservada se nada mudou e a nova validação passa. Uma rejeitada que passa por
nova validação volta a `validated`.

O fingerprint cobre todo o conteúdo da peça, o produto atual e todas as regras.
Uma alteração torna a validação anterior inaplicável; consultas e tentativas de
aprovação retornam a peça para `draft`. Registros antigos permanecem auditáveis
com o fingerprint. Não existe endpoint de edição nesta etapa. Uma futura edição
deve persistir o conteúdo e aplicar a mesma invalidação. Os testes simulam
alterações diretamente no banco. Mudanças no catálogo e nas regras também exigem
nova validação. A aprovação refaz verificações objetivas como proteção adicional.
Transações SQLite serializam as verificações e gravações de estado.

Valores monetários usam Decimal no Python e strings decimais no JSON e no SQLite.
O cliente não envia preço nem oferta na geração. Esses dados são anexados pelo
backend após obter o texto do gerador; o schema do gerador aceita somente canal,
título, subtítulo e CTA. O mock varia o texto por canal e não interpreta livremente
objetivo, público ou instruções adicionais; esses campos são armazenados no briefing
e são utilizados pelo provedor Gemini opcional.

Nome, identidade textual, cores de referência, estilo do mock, templates, aviso,
expressões e severidades são configurados no JSON local. Consulte o
[guia de configuração](docs/configuracao.md) para campos, padrões, limites da
checagem comercial e [exemplos de alerta/bloqueio](examples/configurable_validation.json).
Não há análise visual ou semântica, nem suporte a múltiplos públicos nesta etapa.
Ao atualizar a configuração, consulte/revalide campanhas antes de revisar:
a assinatura inclui toda a configuração e preserva o histórico anterior.

## Testes

Na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Os testes não acessam serviços externos nem o banco da demonstração. Cobrem os dez
cenários pedidos, invalidação de conteúdo/catálogo/regras, rejeição, CORS, erros,
contrato de geração e OpenAPI. Também cobrem normalização de expressões,
severidades, bloqueios comerciais em texto, configuração inválida e personalização
do mock. Os 27 testes originais foram preservados.

## Configurar ou substituir o provedor

Implemente `GenerationService.generate(briefing, product) -> list[GeneratedText]`
em `app/services/generation.py`. Devolva exatamente uma peça por canal solicitado.
Injete a implementação via `create_app(generator=MeuProvedor())` e aponte o Uvicorn
para essa aplicação. Não altere as rotas nem permita campos comerciais na saída
do gerador. O catálogo continua sendo a fonte de preço/oferta e a validação
continua obrigatória. Gemini já está disponível via `GENERATION_PROVIDER=gemini`;
consulte [configuração, falhas e limitações](docs/geracao-ia.md).
