# Continuação explícita quando um provedor de IA está indisponível

Implementação de 26/10/2026. Não há substituição automática de provedores, novas dependências ou alteração de credenciais/configuração. Os provedores de imagem google, openai, mock e disabled continuam disponíveis.

## Textos

O POST `/campaigns/generate` continua recebendo o mesmo briefing. Depois de erro temporário, timeout ou HTTP 429, a resposta 502 mantém o envelope `error` e inclui em `error.details` uma oferta `demo_token` e, quando conhecido, `retry_after_seconds`. Não se persiste campanha nesse momento.

A interface mantém o briefing e mostra **Continuar com versão demonstrativa**. Somente o clique envia o mesmo briefing para a mesma rota com o parâmetro opcional `demo_token`. O servidor verifica se a oferta corresponde exatamente ao briefing, produto e regras da requisição que falhou, e usa `MockGenerationService.generate_package`. Reutilizar a oferta concluída retorna a mesma campanha. Ofertas inválidas, expiradas ou relativas a outro briefing recebem 409.

O mock global não substitui o Gemini configurado. A resposta e a listagem de campanhas possuem o campo adicional opcional `generation`, persistido no JSON das peças, com provider/model/data. A interface distingue texto Gemini, texto mock demonstrativo e origem não registrada de campanhas antigas. **Retomar briefing** recupera os campos preenchidos sem disparar nova geração.

Não há oferta para erro de briefing (422), autenticação, configuração/modelo inválido, resposta fora do contrato, bloqueio de segurança ou validação. HTTP 400 de provedor passa a ter código específico `GENERATION_PROVIDER_ERROR`/`IMAGE_PROVIDER_ERROR`, em vez de ser confundido com indisponibilidade temporária.

## Imagens

Depois de falha elegível, **Criar peça com imagens disponíveis** envia `use_local_assets: true` ao POST `/pieces/{id}/render`. Esse campo é opcional e falso por padrão. O servidor só aceita a opção depois de erro elegível registrado para a peça; não há fallback para erro de segurança/imagem inválida ou falta de assets. O modo disabled pode oferecer composição local após `IMAGE_PROVIDER_UNCONFIGURED`.

A composição alternativa usa um fundo neutro branco produzido por Pillow e os assets locais já existentes: fotografia autorizada do produto, logo e fonte. Reutiliza o compositor e templates atuais. Não chama Gemini/OpenAI nem gera nova fotografia. Feed e story continuam sendo os canais com templates gráficos; banner permanece textual.

`VisualMetadata.composition_source` identifica `ai`, `local_assets` ou `local_test`; campos opcionais `fallback_reason` e `retry_after_seconds` preservam diagnóstico seguro. O PNG inclui o header `X-Creative-Composition-Source`. A interface exibe a origem separadamente da origem do texto: texto Gemini pode ter composição local, e texto mock pode ter fundo de IA, sempre por ação explícita.

Tentativas de renderização ficam em `_render_job`, separado do conteúdo editorial validado. GET de status continua usando o mesmo contrato RenderStatus. Tentativa que falha não muda o texto, o conteúdo visual aprovado, as validações, as revisões ou a imagem final anterior. O job operacional não participa do fingerprint do conteúdo; as checagens comerciais, visuais e de integridade existentes permanecem intactas. Um novo PNG composto com sucesso substitui o conteúdo visual e exige revalidação conforme o fluxo existente. Não há aprovação automática.

## Cotas, erros e limites

- HTTP 429 não é repetido automaticamente. O mesmo objeto de provedor impede novas chamadas durante o cooldown: 60 segundos por padrão, respeitando Retry-After numérico (1–86400 segundos) quando disponível. Cota diária/billing insuficiente identificada em dados estruturados usa pausa conservadora de 24 horas, não uma previsão exata do reset do provedor.
- Erros temporários mantêm as tentativas limitadas já existentes. Mensagens/bodies brutos de provedores e chaves nunca são encaminhados ao usuário; códigos, tempos de espera e logs de operação continuam disponíveis.
- Cooldowns e ofertas são locais ao processo. Reinício os limpa; múltiplos workers não compartilham esse estado. As ofertas expiram em 30 minutos, são limitadas a 256 entradas e exigem nova tentativa elegível se o briefing/produto/regras mudarem. Essa solução é adequada ao MVP local; coordenação distribuída exigiria armazenamento compartilhado.
- Assets e templates locais precisam existir e atender às regras atuais. O fallback não contorna validação comercial, Brand Guardian ou revisão humana. O fundo local é neutro, não uma geração artística equivalente à IA.
- O fluxo normal continua usando o provedor configurado. Nenhum arquivo .env, banco existente ou volume Docker é alterado pela implementação/testes. Não foi necessária migração do SQLite.

## Arquivos de implementação

- Backend: `app/services/availability.py`, `app/services/gemini.py`, `app/services/image_generation.py`, `app/services/workflow.py`, `app/api/campaigns.py`, `app/api/render.py`, `app/api/images.py`, `app/main.py`, `app/schemas/__init__.py`.
- Frontend: `src/api/services/campaigns.ts`, `src/contracts/api.ts`, `src/features/campaigns/BriefingForm.tsx`, `CampaignCard.tsx`, `PieceVisual.tsx`, `content-origin.ts`, `src/pages/CampaignDetailPage.tsx`.
- Testes: novos `backend/tests/test_explicit_fallback.py` e `paguemenos-FRONT-END/tests/fallback.test.tsx`; expectativas de contrato/HTTP 400 atualizadas nos testes existentes; espera inicial dos testes visuais ampliada de 1 para 5 segundos após timeouts ambientais confirmados pela execução isolada.
- Snapshots OpenAPI de backend, frontend e raiz atualizados. O snapshot da raiz também recebeu os contratos visuais que já existiam, mas ainda estavam ausentes daquele documento histórico.

## Verificação

Testes automatizados usam somente transportes simulados, chaves fictícias, SQLite e arquivos temporários. Não efetuam chamadas reais de IA. Resultado final: **219 testes backend e 33 frontend passaram**, com 1 teste HTTP frontend opt-in ignorado e 1 aviso conhecido de depreciação Starlette/HTTPX. TypeScript, lint, build de produção e verificação de espaços do diff passaram. Comandos e diagnóstico de timeouts ambientais registrados em `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`. A inspeção manual no navegador com provedores reais não foi executada nesta alteração.
