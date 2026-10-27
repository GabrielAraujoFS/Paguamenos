# Personalização de campanhas — 26/10/2026

## Comportamento

- Formulário com tema predefinido ou personalizado (até 120 caracteres), estilo visual independente e preço na publicidade com padrão **Não**.
- Gemini recebe os campos no briefing, com instruções para respeitar objetivo, público, canal, regras da marca e dados autorizados. Tema sazonal não autoriza inventar datas, ofertas nem benefícios médicos. Templates mock continuam excluídos do contexto Gemini.
- Mock mantém os textos determinísticos. O planejamento demonstrativo considera os temas conhecidos e o estilo; não simula criatividade de IA real.
- Preço e oferta completos continuam persistidos e sujeitos às mesmas verificações de catálogo. A projeção para publicação omite o preço e as ofertas que contenham valores ou referência explícita a preço quando `show_price=false`. Os campos internos não são apagados ou reescritos.
- Valores monetários reconhecidos nos textos de uma nova campanha sem preço provocam `GENERATION_CONTRACT_ERROR`, sem persistir campanha e sem autorizar fallback demonstrativo. O Brand Guardian também verifica a preferência em conteúdo já persistido. Conflito com informação obrigatória bloqueia a peça, em vez de remover a informação da marca.
- Pillow usa layout versão 2 nas novas campanhas: fotografia maior, preservada inteira e proporcional, CTA contrastante, hierarquia de fontes, formas geométricas na paleta existente e área de produto adaptada à ausência do preço/oferta. Feed e story mantêm dimensões e margens canônicas.
- Tema e estilo ficam registrados nos metadados de composição. Estilos afetam contornos/arredondamentos; temas locais conhecidos usam variações geométricas simples. O tema personalizado orienta o Gemini; o compositor local não cria ilustrações semânticas novas.
- Campanhas existentes sem os novos campos mantêm preço visível e compositor versão 1. A leitura normaliza apenas a resposta, sem migração nem regravação dos registros antigos. PNGs existentes não são recriados automaticamente.
- Metadados, textos publicados, limites, colisões, assets e integridade continuam verificados. Alterações em conteúdo/preferências/imagem invalidam aprovação atual pelo fingerprint existente; histórico é preservado.
- Fallback continua exclusivamente por clique explícito. Token demonstrativo continua vinculado ao briefing completo; alterar tema/estilo/preço após a falha exige nova tentativa de IA. Falha visual não invalida automaticamente o conteúdo textual ou substitui o PNG aprovado.

## Validação

| Verificação | Resultado |
|---|---|
| Backend completo (`python -m pytest -q -p no:cacheprovider --tb=short`) | 253 passaram |
| Novos testes de personalização (execução específica) | 34 passaram |
| Verificações finais focadas em oferta interna e áreas do PNG | 2 passaram |
| Frontend (`vitest run --pool=vmThreads --maxWorkers=1 --testTimeout=20000`) | 34 passaram; 1 opt-in HTTP ignorado |
| TypeScript (`tsc -b --pretty false`) | Passou |
| Lint (`eslint .`) | Passou |
| Produção (`vite build`) | Passou |
| `git diff --check` | Sem erros |

O backend registrou advertência Starlette/httpx e avisos de enum em fixtures de composição, sem falhas. O registro resumido está em `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`.

Os testes usam SQLite temporário, assets sintéticos e transportes/provedores simulados; nenhuma chamada real de IA. Foram inspecionados visualmente PNGs feed sem preço e story com preço, compostos com assets locais existentes. Isso não substitui o teste manual da interface em navegador nem uma avaliação real da criatividade do Gemini.

## Como testar manualmente

1. Abra **Nova campanha**, selecione um produto e preencha objetivo, público e canais feed/story.
2. Selecione **Verão**, **Acolhedor** e mantenha **Exibir preço: Não**. Gere e abra a campanha; confira tema/estilo e o preço identificado como interno.
3. Gere a peça visual. Se o provedor estiver indisponível, confirme **Criar peça com imagens disponíveis**. Confira que o PNG não contém preço, mantém produto/logotipo/disclaimer e informa a origem local na interface.
4. Valide a campanha, examine todos os resultados do Guardian e aprove com identificação do revisor. Confirme histórico e download.
5. Crie outra campanha com **Personalizado**, informe o tema, selecione **Elegante** e preço **Sim**. Confira no PNG o valor exato do catálogo.
6. Reabra uma campanha antiga: seu comportamento e PNG devem ser mantidos. Uma nova composição concluída deve exigir nova validação/revisão conforme o fluxo existente.
7. Em indisponibilidade textual real, confira que nenhum mock é criado até clicar **Continuar com versão demonstrativa**; tema, estilo e preço devem continuar iguais e o resultado deve indicar origem demonstrativa. Não altere credenciais para provocar erros; os cenários 429/temporários são cobertos por testes simulados.

## Limitações

- Banner continua apenas textual, conforme o fluxo já suportado.
- A composição local trabalha com as fotografias/logotipos/fontes disponíveis; os estilos são variações determinísticas, não uma ferramenta completa de design.
- A verificação comercial textual permanece baseada em padrões reconhecidos; não representa análise semântica completa nem OCR do PNG. Revisão humana continua obrigatória.
- Textos/avisos que não caibam ou conflitem com preço oculto são bloqueados; não são cortados nem removidos para conseguir aprovação.
- O preço publicado com **Sim** é acrescentado pelo compositor a partir do campo interno autorizado; Gemini continua orientado a não escrever valores no texto livre.
- Sem chamadas reais ao Gemini nesta implementação; qualidade criativa real deve ser conferida manualmente com o provedor disponível.
- Branch encontrada: `feature/personalizacao-campanhas`. Nenhuma troca de branch, merge, staging, commit ou push. Arquivo `e revisao de campanhas` preservado e ignorado.

## Arquivos alterados

Backend:
- `backend/app/schemas/__init__.py`
- `backend/app/api/campaigns.py`
- `backend/app/services/publication.py` (novo)
- `backend/app/services/composition.py`
- `backend/app/services/gemini.py`
- `backend/app/services/generation.py`
- `backend/app/services/validation.py`
- `backend/app/services/visual_validation.py`
- `backend/app/services/workflow.py`

Frontend:
- `paguemenos-FRONT-END/src/contracts/api.ts`
- `paguemenos-FRONT-END/src/features/campaigns/BriefingForm.tsx`
- `paguemenos-FRONT-END/src/features/campaigns/briefing-schema.ts`
- `paguemenos-FRONT-END/src/features/campaigns/briefing-errors.ts`
- `paguemenos-FRONT-END/src/features/campaigns/PieceDetail.tsx`
- `paguemenos-FRONT-END/src/pages/CampaignDetailPage.tsx`

Testes:
- `backend/tests/test_personalization.py` (novo)
- `backend/tests/test_brand_configuration.py`
- `backend/tests/test_gemini_generation.py`
- `backend/tests/test_visual_brandguard.py`
- `paguemenos-FRONT-END/tests/briefing.test.tsx`
- `paguemenos-FRONT-END/tests/fallback.test.tsx`

Contratos e documentação:
- `backend/examples/openapi.json`
- `docs/openapi.json`
- `paguemenos-FRONT-END/docs/openapi.json`
- `paguemenos-FRONT-END/docs/API_CONTRACT.md`
- `paguemenos-FRONT-END/docs/FRONTEND_ARCHITECTURE.md`
- `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`
- `docs/personalizacao-campanhas.md` (este relatório)
