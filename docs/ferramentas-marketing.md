# Ferramentas de marketing — Zyntra AI

Data: 26/10/2026. Branch mantida: `feature/personalizacao-campanhas`.

## Implementado

### Brand Guardian recolhível

O resumo permanece visível: conformidade, quantidade de verificações aprovadas, violações críticas e demais apontamentos. O relatório detalhado usa `details/summary` nativo, inicialmente recolhido, operável por teclado e leitores de tela. Todas as regras originais continuam disponíveis, agrupadas em composição visual, produto/condições comerciais, limites e identidade da marca. Resultado e severidade são apresentados separadamente. Validações antigas permanecem no histórico; relatório desatualizado recebe aviso.

### Edição restrita

Título, subtítulo e CTA podem ser salvos com identificação do editor. Produto, nome oficial, preço do catálogo, oferta e disclaimer não são campos editáveis. O backend rejeita campos extras, textos vazios, excesso de caracteres e condições comerciais reconhecidas incompatíveis com catálogo/preferência de preço. As demais regras de marca continuam sendo verificadas na validação normal; salvar não significa aprovar.

A edição exige a versão carregada da peça (`expected_version`); conflito ou composição em andamento retorna 409. Alteração relevante coloca a peça em rascunho e registra antes/depois, editor e data, sem apagar validações ou revisões. Salvar sem alteração preserva o estado. A imagem antiga continua consultável; com imagem existente, validar/aprovar exige recomposição explícita antes da nova validação e revisão humana.

As instruções adicionais do briefing continuam preservadas. Não foi adicionado um campo de instruções criativas por peça: o modelo atual guarda essas instruções na campanha e a edição não executa nova geração Gemini. Um campo sem efeito seria enganoso; alteração do briefing/regeneração assistida fica fora desta etapa.

### Ajustes visuais autorizados

O editor oferece os templates existentes `produto_centro`/`produto_direita`, cinco estilos e publicação do preço autorizado. O compositor continua responsável por dimensões, assets, áreas seguras, proporções e colisões; não há coordenadas livres nem arrastar/soltar. A versão 3 é usada em novas composições após edição/upload e diferencia o posicionamento à direita. As versões 1 e 2 mantêm a geometria anterior para não invalidar PNGs existentes.

O botão existente **Recompor com fundo existente** é reutilizado. Salvar ou enviar um fundo não inicia renderização, IA nem fallback automaticamente. Uma nova composição recebe outro ID e hash; versões anteriores permanecem armazenadas, consultáveis e baixáveis pelo histórico, identificadas como históricas.

### Upload funcional como fundo

Disponível no editor para feed/story. Reutiliza `LocalImageStorage` e a composição Pillow. Exige identificação e confirmação de autorização de uso. Aceita somente PNG/JPEG reais, estáticos, até 5 MiB, entre 256 e 4096 pixels por lado e até 12 milhões de pixels. O limite é aplicado durante a leitura do corpo; dimensões são verificadas antes da decodificação completa. Conteúdo inválido, animação, incompatibilidade de formato e excesso de limites são recusados.

O servidor verifica o arquivo, aplica a orientação EXIF e regrava PNG sem os metadados originais. O armazenamento usa ID opaco, hash SHA-256 normalizado e hash do arquivo original; registra peça/campanha, origem `uploaded`, identificação e autorização declaradas, data e dimensões. Nenhum nome de arquivo do cliente é usado como caminho. Assets já vinculados não são removidos.

A recomposição usa efetivamente a referência selecionada, sem solicitar fundo à IA; o teste compara hash e pixels do fundo recebido com a saída. O fundo pode ser recortado para preencher feed/story, como os fundos existentes. Produto e logo oficiais continuam inseridos pelo compositor, sem serem substituídos pelo upload. A interface e o PNG via cabeçalho identificam a origem enviada pela equipe. O Guardian verifica integridade e os metadados de origem/autorização.

O Nginx do frontend recebeu `client_max_body_size 5m` em `/api/`, alinhado ao limite do backend; seu padrão anterior impediria uploads válidos acima de 1 MiB. Dockerfile e Compose não foram alterados. É necessário reconstruir/reimplantar o frontend para aplicar essa configuração; isso não foi executado nesta tarefa.

## Contratos

| Operação | Contrato |
|---|---|
| **Novo** `POST /pieces/{piece_id}/edit` | JSON `PieceEdit`: expected_version, editor_id, title, subtitle, cta, show_price, visual_style opcional/nulo e template opcional. Retorna `Piece`. |
| **Novo** `POST /pieces/{piece_id}/background` | Corpo binário PNG/JPEG; query editor_id, rights_confirmed=true, expected_version. Retorna `Piece` com selected_background; não compõe automaticamente. |
| **Alterado** `GET /pieces/{piece_id}/image` | Query opcional version_id, restrita a imagens vinculadas à própria peça. Sem query, preserva a imagem atual. Versões anteriores são identificadas por cabeçalho de estado `historical`. |
| **Reutilizado** `POST /pieces/{piece_id}/render` | Contrato de entrada mantido; force=true recompõe usando o fundo selecionado ou o existente. Registra origem uploaded quando aplicável. |
| **Reutilizados** campanha/validate e peça/review | Regras e transições anteriores preservadas; nova proteção impede aprovar arte desatualizada ou upload ainda não aplicado. |

`Piece` ganhou campos aditivos: edit_version, edit_history, visual_history, visual_needs_recomposition e selected_background. Composition_version também aceita 3; composition_source aceita uploaded. Os três snapshots OpenAPI foram exportados do app FastAPI. Persistência continua no JSON da peça, sem migração de banco.

## Referência criativa para IA: verificação e proposta

O adaptador textual atual (`backend/app/services/gemini.py`) envia somente `contents.parts.text` com contexto JSON. O serviço Google de fundos também recebe um prompt textual. Não há envio de bytes de imagem para interpretação nesses caminhos. O upload implementado nesta etapa não passa nome, caminho ou imagem ao Gemini e não afirma interpretação visual.

Proposta futura, condicionada à confirmação de suporte multimodal do modelo configurado na documentação oficial:

1. Adicionar uma operação distinta, com consentimento explícito para enviar a imagem ao provedor; não reutilizar o upload como se já fosse uma referência interpretada.
2. Resolver apenas a imagem normalizada vinculada à peça, verificar integridade/limites e transmitir seus bytes reais em um conteúdo multimodal suportado. Nunca enviar caminhos locais ou aceitar URLs arbitrárias.
3. Tratar imagem e briefing como dados não confiáveis; regras de marca, catálogo e política comercial continuam prioritários. Resposta estruturada passa pelas validações existentes, sem aprovação automática.
4. Registrar modelo, hash da referência, horário e origem. Falha mantém a peça e o fundo, com as opções explícitas já existentes; nenhuma cobrança ou chamada automática ao anexar arquivo.
5. Testar transporte simulado confirmando bytes/MIME reais, ausência de chave nos payloads/logs de diagnóstico, recusa de assets inválidos/não vinculados, resposta fora do contrato, segurança, 429/timeout/503, integridade, persistência e invalidação de aprovação. A avaliação visual real e de criatividade exige teste manual autorizado com o provedor.

Essa proposta não foi implementada e não houve consumo de APIs externas.

## Testes e evidências

| Verificação final | Resultado |
|---|---|
| Backend completo: `python -m pytest -q -p no:cacheprovider --tb=short` | **284 passaram** |
| Arquivo específico de marketing | **31 passaram** |
| Frontend completo: `vitest run --pool=vmThreads --maxWorkers=1 --testTimeout=20000` | **39 passaram; 1 HTTP opt-in ignorado** |
| TypeScript: `tsc -b --pretty false` | **Passou** |
| Lint: `eslint .` | **Passou** |
| Produção: `vite build` | **Passou** |
| `git diff --check` | **Sem erros** |

Os testes usam provedores simulados, chaves sintéticas e SQLite/assets temporários. Nenhuma chamada real ou crédito de Gemini/OpenAI foi consumido. A suíte completa cobre também o fallback explícito e a revisão humana anteriores. Os casos novos cobrem conteúdo/condições comerciais, invalidação, recomposição/histórico, conflitos, upload PNG/JPEG, orientação/remoção de metadados, arquivos inválidos/animados/grandes, hashes, persistência, versões antigas e metadados danificados.

O backend registrou a advertência preexistente Starlette/httpx e avisos de enum em fixtures de composição, sem falhas. No desenvolvimento, o lint identificou um callback de formulário corrigido antes da execução final. O teste de details foi ajustado para conferir o atributo open, sem presumir que jsdom remove os nós recolhidos.

A configuração Nginx foi ajustada para 5m; não havia executável nginx local para teste de sintaxe e containers não foram reconstruídos. O teste completo da interface no navegador e do upload pelo proxy Docker permanece no roteiro manual. O registro resumido está também em `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`.

## Limitações

- Os estilos/posicionamentos do editor ajustam a composição determinística. Salvar não reescreve o prompt original do fundo nem executa novo planejamento criativo Gemini; uma nova geração de fundo continua baseada nesse prompt original.
- Sem editor livre, controle de coordenadas, substituição de foto oficial/logo, upload para banner ou interpretação multimodal. O upload entra pela edição de peça, após a criação da campanha.
- Direitos e identidade do editor/uploader são autodeclarados, como reviewer_id no MVP; não há novo sistema de autenticação. A imagem enviada ainda exige revisão humana de conteúdo, direitos e adequação de marca.
- Verificação visual determinística não é OCR, antivírus geral nem análise semântica de alegações/logos dentro de uma fotografia. O arquivo é decodificado e normalizado como imagem antes do uso; regras existentes e revisão humana permanecem.
- Sem restauração automática de uma versão anterior: o histórico permite consulta/download e antes/depois. Arquivos anteriores não são apagados.
- Falhas de rede não têm retry automático. Se o servidor tiver concluído a gravação sem o cliente receber a resposta, atualizar e conferir o histórico antes de repetir. Versões antigas são recusadas com conflito.
- A validação comercial continua baseada em padrões reconhecidos. O editor não autoriza novas ofertas nem altera o catálogo para conseguir aprovação.
- Não foi realizado teste manual completo no navegador nem reconstrução dos containers Docker nesta tarefa; os cenários automatizados não substituem essas verificações.

## Roteiro manual

1. Abra uma campanha existente. Valide e confira o resumo do Guardian; use Tab/Enter/Espaço no controle do relatório para expandir/recolher e confira categorias, severidades e verificações individuais.
2. Abra **Editar peça**, informe sua identificação e altere título, subtítulo e CTA. Salve. Confira rascunho, aviso de revalidação e histórico antes/depois; preço/oferta oficiais devem permanecer iguais.
3. Selecione estilo e posicionamento autorizado e habilite/desabilite a publicação de preço. Salve e clique explicitamente em **Recompor com fundo existente**. Confira nova arte, fotografia sem cortes, logo/disclaimer, margens e adequação de feed/story.
4. Abra **Versões visuais anteriores**, consulte/baixe a arte anterior e confira que ela não representa a aprovação atual. Valide a nova peça e registre uma nova revisão humana.
5. Abra o editor, informe identificação e selecione PNG/JPEG dentro dos limites. O envio deve ficar bloqueado até confirmar a autorização. Clique em **Enviar e selecionar fundo**; a imagem atual ainda deve estar preservada.
6. Clique em **Recompor com fundo existente**. Confira que o fundo é o arquivo escolhido, que a origem é **Fundo enviado pela equipe**, e que produto/logo oficiais permanecem. Valide, revise e baixe o PNG.
7. Repita com JPEG de celular com orientação EXIF. Tente arquivo inválido e imagem fora dos limites: deve haver erro claro, sem perda do trabalho anterior.
8. Abra a mesma peça em duas abas, salve numa e tente salvar a versão antiga na outra. A segunda deve receber conflito, sem sobrescrever silenciosamente.
9. Confira uma campanha antiga sem plano visual: edição de texto continua disponível; em feed/story, o editor pode criar um plano local autorizado para composição, sem gerar texto ou imagem por IA.
10. Em falha real de provedor, confirme que as opções demonstrativa/local ainda dependem de clique, continuam identificadas e não apagam histórico ou decisões humanas. Os erros de cota/temporários já têm cobertura simulada; não altere credenciais para provocar erros.

Nenhum commit, merge, push, staging, alteração de credenciais/.env, exclusão de banco, imagem ou volume foi realizado. O arquivo `e revisao de campanhas` permaneceu fora das alterações.


## Arquivos alterados

- `backend/app/api/editing.py`
- `backend/app/api/images.py`
- `backend/app/api/render.py`
- `backend/app/main.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/composition.py`
- `backend/app/services/uploads.py`
- `backend/app/services/visual_validation.py`
- `backend/examples/openapi.json`
- `backend/tests/test_brand_configuration.py`
- `backend/tests/test_marketing_workflow.py`
- `docs/ferramentas-marketing.md`
- `docs/openapi.json`
- `paguemenos-FRONT-END/docs/API_CONTRACT.md`
- `paguemenos-FRONT-END/docs/FRONTEND_ARCHITECTURE.md`
- `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`
- `paguemenos-FRONT-END/docs/FRONTEND_ROADMAP.md`
- `paguemenos-FRONT-END/docs/openapi.json`
- `paguemenos-FRONT-END/nginx.conf`
- `paguemenos-FRONT-END/src/api/services/campaigns.ts`
- `paguemenos-FRONT-END/src/contracts/api.ts`
- `paguemenos-FRONT-END/src/features/campaigns/PieceDetail.tsx`
- `paguemenos-FRONT-END/src/features/campaigns/PieceEditor.tsx`
- `paguemenos-FRONT-END/src/features/campaigns/PiecePreview.tsx`
- `paguemenos-FRONT-END/src/features/campaigns/PieceVisual.tsx`
- `paguemenos-FRONT-END/src/features/campaigns/ValidationResults.tsx`
- `paguemenos-FRONT-END/tests/campaign-services.test.ts`
- `paguemenos-FRONT-END/tests/marketing-tools.test.tsx`
