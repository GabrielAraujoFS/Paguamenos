# Composição local com Pillow

`PillowComposer` monta uma peça a partir do texto e preço autorizados de `Piece`, um fundo salvo em `LocalImageStorage`, uma fotografia PNG do produto, um logotipo PNG e uma fonte TTF/OTF. Nenhuma chamada de IA ocorre neste serviço. O retorno é uma `ImageReference` de PNG final. Erros identificáveis usam `CompositionError.code` (`BACKGROUND_MISSING`, `PRODUCT_ASSET_MISSING`, `LOGO_MISSING`, `FONT_MISSING`, `FONT_INVALID`, `TEXT_OVERFLOW`, `LAYOUT_COLLISION`, `LAYOUT_OUT_OF_BOUNDS`, `TEMPLATE_INVALID`, `TEMPLATE_UNSUPPORTED`).

Use `default_template("produto_centro", Channel.FEED)` ou `default_template("produto_direita", Channel.STORY)`. Os dois layouts aceitam Feed 1080 × 1350 e Stories 1080 × 1920. `TemplateConfig.safe_area` configura margens `left`, `right`, `top`, `bottom`; `min_font_size` e `max_font_size` limitam o ajuste de texto. Dimensões fora desses dois formatos são rejeitadas. O fundo é recortado ao centro; produto e logo mantêm a proporção.

Assets de produção devem ficar em `app/data/assets/product_photographs/<product_id>.png`, `app/data/assets/logos/logo.png` e `app/data/assets/fonts/brand.ttf`. Os READMEs nessas pastas registram as ausências atuais. O compositor não seleciona substitutos para assets ausentes. A fonte demonstrativa do sistema é usada apenas nos testes e no script de demonstração.

`compose_model(piece_model, background, template)` grava as referências e o estado `composed` no JSON `PieceModel.content.visual`; o chamador deve confirmar a transação. O sidecar do PNG final guarda fundo, produto, template, dimensões, data e estado, e o storage registra SHA-256. Alterações no JSON entram no fingerprint existente do BrandGuard e exigem revalidação antes da aprovação.

## Renderização por peça

`POST /pieces/{piece_id}/render` inicia uma tarefa local após conferir fotografia PNG, logo e fonte. Corpo `{}` reutiliza o fundo da própria peça quando existir; `{"force": true}` recompõe com o mesmo fundo; `{"regenerate_background": true}` solicita um novo fundo; `{"source_piece_id": "..."}` reutiliza o fundo de outra peça do mesmo canal e campanha. `request_id` (UUID) opcional torna reenvios identificáveis. `GET /pieces/{piece_id}/render` retorna o estado e os metadados visuais. Não há novo fluxo de campanha nem publicação automática.

O POST devolve 202 quando agenda o trabalho, 200 quando a peça já está pronta ou quando assets ausentes deixam o estado `blocked`. A tarefa em processo usa `processing` e `background_ready`, terminando em `composed` ou `failed`. Consulte o GET até a conclusão. O estado e os erros ficam no JSON existente da peça; a campanha e seus textos são preservados. Uma mudança no conteúdo exige a validação BrandGuard atual antes da aprovação.

O executor usa `BackgroundTasks` no próprio processo FastAPI. Não garante entrega se o processo encerrar; na próxima inicialização um trabalho interrompido passa a `failed` para permitir nova solicitação. Em múltiplos processos não há coordenação distribuída. A verificação de assets ocorre antes da chamada externa, e a chamada não mantém transação SQLite aberta. A revisão visual continua necessária: a API não consegue garantir por OCR que o fundo não contenha texto, logo ou produto indesejado. Rejeite a peça na revisão humana e solicite `regenerate_background` quando isso ocorrer.

## Provedor Google de fundos

O padrão é `IMAGE_GENERATION_PROVIDER=disabled`. Para habilitar: `IMAGE_GENERATION_PROVIDER=google`, `GEMINI_API_KEY`, `IMAGE_MODEL=gemini-3.1-flash-image`, `IMAGE_SIZE=2K`, `IMAGE_TIMEOUT_SECONDS=120` e `IMAGE_MAX_ATTEMPTS=2`. O SDK oficial `google-genai==2.33.0` solicita somente imagem, proporção 4:5 para Feed ou 9:16 para Stories. `gemini-3.1-flash-lite-image` é aceito somente com `IMAGE_SIZE=1K`. A estimativa de USD no metadata usa equivalentes publicados por imagem, não uma cobrança confirmada; ela não inclui todos os possíveis componentes da fatura e pode mudar.

Para um teste real de **uma única geração paga de fundo**, instale assets autorizados, mantenha `GENERATION_PROVIDER=mock`, configure `IMAGE_GENERATION_PROVIDER=google` e `IMAGE_MAX_ATTEMPTS=1`, crie uma campanha com apenas Feed ou Stories e faça um POST render com `{}` uma vez. Consulte o GET e os metadados antes de qualquer nova tentativa. Não use `regenerate_background` no teste inicial. Nenhum teste automatizado chama a API externa.

Documentação oficial consultada para o modelo, o SDK e estimativas: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image, https://ai.google.dev/gemini-api/docs/generate-content/image-generation, https://ai.google.dev/gemini-api/docs/pricing e https://googleapis.github.io/python-genai/.

## Provedor OpenAI e mock de fundos

Selecione `IMAGE_GENERATION_PROVIDER=openai` e configure `OPENAI_API_KEY` no backend (ou `.env` do Docker Compose). O serviço usa exatamente `gpt-image-1-mini` por `POST /v1/images/generations`, com PNG, uma imagem, qualidade média e dimensão retrato 1024 × 1536 para Feed e Stories. O Pillow recorta o fundo ao formato final do template. `IMAGE_MODEL` e `IMAGE_SIZE` continuam sendo opções do Google e não alteram o modelo ou dimensão OpenAI. `IMAGE_TIMEOUT_SECONDS` e `IMAGE_MAX_ATTEMPTS` continuam controlando o limite de espera e tentativas; 401/403, 429, timeout, indisponibilidade, falha de armazenamento e PNG inválido geram códigos sanitizados. Não há fallback silencioso para Google. O PNG é salvo em `IMAGE_STORAGE_ROOT` com ID opaco, SHA-256 e metadados de geração; o texto e os dados comerciais existentes não são alterados.

Para teste sem API externa, use `IMAGE_GENERATION_PROVIDER=mock` e `IMAGE_MOCK_PATH` apontando para um PNG existente **dentro do ambiente do backend**. O mock usa o `LocalImageBackgroundGenerator` já disponível. O padrão segue `disabled`.

Esta branch inclui `app/data/assets/backgrounds/mock-background.png`, um fundo abstrato demonstrativo criado localmente, sem texto ou produto. No Docker Compose, basta definir `IMAGE_GENERATION_PROVIDER=mock`; o caminho já aponta para esse arquivo. Em execução local, defina `IMAGE_MOCK_PATH=./app/data/assets/backgrounds/mock-background.png` a partir da pasta `backend`. O arquivo é apenas para testes e não representa um fundo criado por IA.

`gpt-image-1-mini` é o modelo solicitado, mas a [página oficial do modelo](https://developers.openai.com/api/docs/models/gpt-image-1-mini) atualmente o marca como depreciado. A [referência oficial de geração](https://developers.openai.com/api/reference/resources/images/methods/generate) ainda o lista entre os modelos aceitos; disponibilidade depende da conta. Nenhum teste automatizado consome a API externa.

## Testar com Docker

Na raiz do repositório, com Docker Desktop ativo:

```powershell
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest -q -p no:cacheprovider tests/test_composition.py tests/test_visual_infrastructure.py
```

Para gerar uma imagem **sintética, não publicável**:

```powershell
cd backend
python -m examples.render_demo
```

O script grava `creative-assets/demo-creative.png` e usa somente imagens desenhadas no próprio script. No Docker, execute `docker compose run --rm --no-deps backend python -m examples.render_demo`; o arquivo fica no volume persistente de imagens em `/data/creative-assets`. A demonstração local usa `backend/creative-assets` e não é versionada.
