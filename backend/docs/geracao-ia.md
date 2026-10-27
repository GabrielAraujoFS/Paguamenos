# Geração textual e direção visual: mock e Gemini

Os sete endpoints, schemas públicos e tabelas permanecem iguais. O padrão é
`mock`, local, determinístico e sem chave. Gemini é opcional e só chama a API
quando POST /campaigns/generate é solicitado. A integração Gemini reutiliza
HTTPX e Pydantic, sem dependências adicionais para o provedor.

No fluxo de campanha, mock e Gemini retornam texto e um `VisualPlan` para cada
canal Feed/Stories. O adaptador Gemini solicita ambos em uma única resposta JSON
estruturada; `GeminiGenerationService.generate()` continua disponível para uso
textual direto. O plano e os metadados (modelo, tentativas e contagem de tokens
quando fornecida) são guardados em `PieceModel.content.visual`, sem novos campos
na resposta pública. Banner mantém a geração textual e não recebe plano visual,
pois o compositor atual suporta somente Feed e Stories. Nenhuma imagem é gerada
nesta etapa.

O backend aceita apenas `produto_centro` e `produto_direita` e acrescenta ao
prompt de fundo as áreas livres do template e proibições explícitas de texto,
preço, logotipo, embalagem, produto fictício e marca d'água. Planos com termos
comerciais detectáveis, campos ausentes ou canais inesperados são rejeitados.
`VISUAL_MAX_ATTEMPTS` limita a 1–3 as tentativas de resposta estruturada
(padrão 2); erros 401/403 e 429 não são repetidos.

## Executar com mock

Na pasta backend, em PowerShell:

```powershell
$env:GENERATION_PROVIDER = 'mock'
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Executar com Gemini

Crie uma chave em https://aistudio.google.com/apikey usando um projeto no nível
gratuito. Confirme o nível e as cotas no painel; o código não controla faturamento
nem garante que uma chave pertence ao Free Tier. Para avaliação exclusivamente
gratuita, não ative faturamento pago. Disponibilidade e cotas dependem da conta
e do modelo. Ao atingir a cota, a aplicação retorna erro, sem trocar de provedor.

Na pasta backend, em PowerShell:

```powershell
$env:GENERATION_PROVIDER = 'gemini'
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
$env:GENERATION_TIMEOUT_SECONDS = '20'
$geminiKeyInput = Read-Host 'Chave Gemini (entrada oculta)' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiKeyInput).Password
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Após encerrar o servidor:
Remove-Item Env:GEMINI_API_KEY
```

Nunca envie a chave ao frontend, chat, logs ou Git. Não há carregamento automático
de .env. Reinicie o servidor após mudar variáveis. Chave ausente ou configuração
inválida impede iniciar em modo Gemini. O mock ignora variáveis Gemini não usadas.
create_app(generator=...) continua tendo prioridade sobre o ambiente.

GET /health retorna generation_provider=gemini quando o adaptador está
configurado; isso não comprova conectividade, validade da chave nem gratuidade.

## Conteúdo e Guardian

O modelo recebe briefing, produto e regras locais: identidade, tom, público,
objetivo, canal, limites e mensagens obrigatórias/proibidas. As instruções do
briefing são tratadas como dados, sem autoridade para substituir as regras.
Pede-se JSON Schema com uma peça por canal: title (chamada), subtitle (legenda)
e cta. A resposta é validada novamente com Pydantic. Campos extras e canais
incompatíveis são rejeitados. O backend insere preço, oferta, nome e aviso das
fontes locais autorizadas. O prompt pede que textos livres não contenham ofertas,
preços nem alegações de saúde inventadas.

Peças continuam em draft; use a validação existente e depois revisão humana.
O Guardian mantém severidades, bloqueios críticos, fingerprints e histórico.
JSON válido não significa aprovação. As checagens são sintáticas e limitadas:
não detectam semanticamente toda alegação de saúde ou promoção inventada.

Não há imagens, edição, correção automática, publicação ou múltiplas alternativas
por canal/público. Dados continuam sintéticos, sem atribuição oficial à Pague
Menos. No nível gratuito o conteúdo pode ser usado para melhorar produtos Google;
utilize somente dados sintéticos autorizados nesta avaliação.

## Falhas e rastreabilidade

Falhas externas previstas usam HTTP 502 e o envelope error existente:

| error.code | Significado |
|---|---|
| GENERATION_AUTH_ERROR | HTTP 401/403 do provedor |
| GENERATION_RATE_LIMIT | HTTP 429, cota ou limite |
| GENERATION_TIMEOUT | Espera de rede excedida |
| GENERATION_UNAVAILABLE | Falha de transporte ou outro HTTP sem sucesso |
| GENERATION_CONTRACT_ERROR | Saída vazia, bloqueada, incompleta, JSON/campos/canais inválidos |

Não há repetição automática nem fallback. Falha de geração não persiste campanha.
Timeout HTTPX é por operação de rede, não prazo total absoluto; padrão de 20
segundos, configurável entre zero (excluído) e 120 segundos. Saída limitada a
4096 tokens. A chamada externa ocorre antes de adquirir conexão/transação SQLite;
validação e revisão mantêm sua serialização existente.

Logs da aplicação registram operação, provedor, modelo, duração e campanha após
o flush (o commit ocorre ao finalizar a requisição); falhas previstas usam código
sanitizado. Não habilite logs HTTP de depuração que exponham cabeçalhos/conteúdo.
Provedor/modelo não são persistidos por campanha: rastreabilidade da geração é
operacional por logs; a auditoria persistida continua cobrindo conteúdo,
validações e revisões.

O logger `app.api.campaigns` emite sucesso em INFO e falhas previstas em WARNING.
A configuração padrão do Uvicorn não habilita INFO para o logger da aplicação;
por isso o terminal pode mostrar apenas acessos HTTP. O campo provider dos logs
usa o nome da classe (`GeminiGenerationService`), enquanto /health usa `gemini`.
Essa limitação de exibição não indica fallback. Habilitar logs da aplicação é
uma melhoria de observabilidade separada; não exponha a chave para comprovar uso.

## Testes

```powershell
$env:GENERATION_PROVIDER = 'mock'
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Os testes usam MockTransport e bancos temporários, sem chave nem chamadas reais.
Cobrem sucesso, erros, respostas inválidas, ausência de fallback, Guardian,
revisão e aquisição independente do bloqueio SQLite durante a geração.
A suíte original mantém comparação integral do OpenAPI e invalidação/histórico.

Para verificação real, configure Gemini e siga o roteiro Swagger do README:
gerar → validar → revisar. Confira texto, preço estruturado, avisos e falhas.
Essa verificação depende da chave e cotas e não integra a suíte automatizada.
O responsável pelo backend confirmou esse fluxo real no Swagger na Sprint 3.

Referências consultadas em 23/10/2026:
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits
