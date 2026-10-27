# Integração das fotografias de produtos — 26/10/2026

Branch mantida: `feature/personalizacao-campanhas`. As alterações de marketing já existentes no workspace foram preservadas.

## Fotografias e associação

Os cinco PNGs fornecidos em `assets/produtos/` foram abertos, verificados com Pillow e inspecionados visualmente antes da integração. Todos são RGB, com cenário próprio; nenhuma transparência foi presumida. As cópias em `backend/app/data/assets/product_photographs/` são idênticas, byte a byte, aos originais. Não houve geração, remoção de fundo ou edição dos arquivos.

| ID confirmado no catálogo | Produto | Arquivo | Dimensões |
|---|---|---|---|
| syn-001 | Sabonete Brisa | sabonete_brisa.png | 485 × 348 |
| syn-002 | Shampoo Aurora | shampoo_aurora.png | 486 × 348 |
| syn-003 | Hidratante Nuvem | hidratante_nuvem.png | 484 × 348 |
| syn-004 | Escova Sorriso | escova_sorriso.png | 736 × 324 |
| syn-005 | Algodão Sereno | algodao_sereno.png | 740 × 324 |

O registro `backend/app/data/assets/product_photographs/photos-2026-10.json` associa IDs, nomes de arquivo e SHA-256. `products.json`, nomes, descrições, categorias, preços, ofertas e regras comerciais não foram alterados.

## Compatibilidade e aprovações

Substituir os arquivos antigos `syn-001.png` etc. faria o Guardian detectar alteração de hash e invalidar aprovações. Por isso esses arquivos foram mantidos intactos. Nenhuma imagem persistida, referência histórica, campanha ou aprovação foi regravada pela integração.

Novas campanhas registram `Piece.product_photo_version=photos-2026-10` quando o pacote de fotografias está disponível no compositor. Peças existentes sem esse campo usam a versão `legacy`, incluindo quando são consultadas ou recompostas explicitamente. Não há migração nem atualização automática para uma foto diferente. Uma nova campanha é o caminho para usar a nova versão.

O teste de compatibilidade aprova uma peça sem o campo de versão, registra seu fingerprint/PNG, instala o novo pacote e confirma: conteúdo persistido igual, fingerprint igual, aprovação mantida, mesma quantidade de revisões e mesmo PNG. A revalidação dessa peça também mantém a aprovação quando nada mudou.

## Frontend e endpoint

Nova rota **GET `/products/{product_id}/image`** serve somente a fotografia registrada para um produto existente. Confere PNG e hash, retorna `image/png`, ETag com SHA-256, `Cache-Control: no-cache` e `X-Content-Type-Options: nosniff`. Produto/arquivo ausente retorna 404; corrupção ou registro inválido retorna 409. Não aceita caminhos nem nomes de arquivos enviados pelo cliente.

O componente compartilhado `ProductPhoto` foi incluído no cartão e no detalhe do produto. Usa texto alternativo com o nome do produto, carregamento lazy, quadro uniforme 4:3 e `object-contain`. Assim mantém a proporção e a fotografia inteira, inclusive nos arquivos horizontais. Em erro, apresenta placeholder acessível e conserva os dados e a navegação.

A URL vem do cliente de API existente: no desenvolvimento, `http://127.0.0.1:8000/products/{id}/image` por padrão; no build Docker, `/api/products/{id}/image`. A listagem de produtos mantém seu contrato comercial anterior; somente Piece ganhou o campo aditivo de versão. Os três snapshots OpenAPI foram exportados novamente do aplicativo real.

## Compositor e Brand Guardian

O PillowComposer resolve o asset pelo ID e pela versão persistida. As novas fotos são apresentadas por inteiro em um cartão fotográfico com borda/painel nas cores já autorizadas. O cenário da fotografia permanece intacto. O redimensionamento mantém a proporção; a área reservada ao produto continua sujeita às mesmas verificações de dimensões, template, margens e colisões. Os elementos decorativos destinados a uma embalagem recortada não ficam atrás do novo cartão.

A cópia persistida `product_asset` contém os bytes completos da foto original. A composição registra nome do asset, versão, apresentação `photo_card`, ID e SHA-256. O Guardian reutiliza a validação de asset/hash e acrescenta a correspondência desses metadados com o registro. Confere o hash fixado no registro e o arquivo autorizado atual; trocar produto/foto, corromper o arquivo ou adulterar os metadados bloqueia a aprovação. Logo, fontes, PNG, textos, informações comerciais e revisão humana continuam verificados.

O fingerprint de fotos legadas continua calculado com o mesmo arquivo e os mesmos hashes anteriores. Não foi criada exceção para permitir divergência de hash. Para as fotos novas, corrupção é reportada na verificação visual antes de solicitar fundo a um provedor; a geração textual não é convertida silenciosamente para outro provedor.

## Docker e reconstrução

O backend já usa `COPY app ./app`; as fotos e o registro agora ficam dentro desse contexto e são incluídos na imagem. O frontend usa a mesma rota pelo proxy `/api/` do Nginx. Não há dependência dos caminhos Windows em execução, cópias de fotos no bundle frontend ou alteração de Dockerfile/Compose/volumes.

Para aplicar na sua instalação, a partir da raiz do projeto:

```powershell
docker compose build backend frontend
docker compose up -d backend frontend
```

O segundo comando recria os serviços com as imagens novas, preservando os volumes nomeados existentes. Faça isso quando estiver pronto para interromper/reiniciar os serviços. Não é necessário executar down, remover volumes ou apagar bancos/imagens.

A verificação desta tarefa usa imagens separadas `zyntra-photos-backend:verification` e `zyntra-photos-frontend:verification`, além de um projeto temporário com banco em memória e sem volumes. A instalação real não foi substituída. Os dois containers temporários e sua rede foram encerrados após os testes; a consulta final confirmou que não restaram containers desse projeto. Nenhum volume foi criado ou removido por essa verificação.

## Validação

- Backend completo: **316 testes passaram** (`python -m pytest -q -p no:cacheprovider --tb=short`).
- Casos específicos das fotos: **32 passaram** no Windows e **32 passaram no container Linux sem rede**.
- Frontend completo: **47 passaram, 1 HTTP opt-in ignorado** (`vitest run --pool=vmThreads --maxWorkers=1 --testTimeout=20000`).
- TypeScript, lint e build de produção: **passaram**.
- Build Docker backend/frontend: **passaram**. `nginx -t` passou no ambiente isolado.
- As fotos foram conferidas no catálogo real no navegador, servido pelo Docker. Feed sem preço e story com preço foram compostos e inspecionados visualmente.
- HTTP/Nginx isolado confirmou os cinco PNGs/hashes e um fluxo completo: geração mock, provider visual desabilitado, composição local solicitada explicitamente, Guardian, revisão de teste e exportação de PNG (714145 bytes).
- Testes cobrem associação, catálogo sem alteração comercial, bytes/hash, PNG exportado, fotografia integral e proporcional, cinco produtos, feed/story, preço oculto/visível, placeholders, URLs local/proxy, corrupção e aprovação antiga preservada.
- Nenhum teste usa APIs reais de IA. Os avisos de depreciação Starlette/httpx e de enum em fixtures de composição já existentes permanecem, sem falhas.

O primeiro teste de preço dos cartões usou Intl e um espaço não separável diferente do formatador atual. A comparação do teste foi corrigida; o formatador e os preços do catálogo não foram alterados.

## Roteiro manual

1. Após reconstruir, abra **Catálogo / Produtos disponíveis** em `http://localhost:5173/products`. Confira a associação das cinco fotos, nome, categoria, descrição, preço e link Ver produto.
2. Confira a mesma página em janela estreita e larga. Fotos horizontais devem aparecer inteiras com margens; isso é intencional para evitar cortes/distorções. O detalhamento também deve mostrar a foto do produto.
3. Crie uma campanha nova para cada produto. Selecione feed/story e preço Não. Gere o texto e a composição; se o provedor visual estiver desabilitado, confirme explicitamente a opção de recursos locais.
4. Confira fotografia, fundo próprio preservado, título/CTA/disclaimer/logo, ausência de preço e ausência de sobreposição. Valide pelo Guardian, revise e baixe o PNG.
5. Repita com preço Sim e confira o valor exato do catálogo. Fotografia e metadados devem continuar correspondendo ao produto.
6. Abra uma campanha aprovada anterior à integração: foto/PNG, aprovação, histórico e download devem permanecer como antes. Não é feita troca automática de foto em campanhas antigas.
7. Para conferir placeholder, use o bloqueio de requisição do navegador na URL de uma foto ou indisponibilidade simulada em desenvolvimento. Não apague/corrompa arquivos da instalação para provocar erros; os cenários de corrupção têm cobertura automática.

## Limitações

- Fotografias horizontais deixam margens em quadros verticais para preservar seu conteúdo. Não há recorte inteligente, remoção de fundo ou aumento de resolução por IA.
- Os arquivos fornecidos têm resolução limitada; ampliar uma foto não cria detalhes adicionais.
- A validação de texto/alegações continua determinística e não é OCR de rótulos dentro da fotografia. Revisão humana permanece obrigatória.
- A inspeção do navegador foi realizada em desktop; o roteiro inclui a conferência manual em telas menores.
- Novas versões devem ser registradas separadamente; não edite os arquivos/hashes das versões já usadas se deseja preservar a aprovação dessas peças.

Não foram alteradas credenciais, .env, configurações de IA, regras comerciais ou dados persistentes. Sem staging, commit, merge ou push. O arquivo não rastreado `e revisao de campanhas` permanece fora desta entrega.


## Arquivos desta etapa

São 27 arquivos criados/atualizados nesta etapa (incluindo fotos e contratos). Os cinco originais fornecidos em assets/produtos foram apenas lidos e permanecem intactos. Os demais arquivos já modificados pela etapa anterior de marketing não foram descartados.

- `backend/app/api/campaigns.py`
- `backend/app/api/products.py`
- `backend/app/api/render.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/composition.py`
- `backend/app/services/visual_validation.py`
- `backend/tests/test_product_photos.py`
- `backend/tests/test_brand_configuration.py`
- `backend/examples/openapi.json`
- `docs/openapi.json`
- `docs/fotografias-produtos.md`
- `paguemenos-FRONT-END/docs/openapi.json`
- `paguemenos-FRONT-END/docs/API_CONTRACT.md`
- `paguemenos-FRONT-END/docs/FRONTEND_ARCHITECTURE.md`
- `paguemenos-FRONT-END/docs/FRONTEND_PROGRESS.md`
- `paguemenos-FRONT-END/src/api/services/products.ts`
- `paguemenos-FRONT-END/src/contracts/api.ts`
- `paguemenos-FRONT-END/src/features/catalog/ProductPhoto.tsx`
- `paguemenos-FRONT-END/src/features/catalog/ProductCard.tsx`
- `paguemenos-FRONT-END/src/pages/ProductDetailPage.tsx`
- `paguemenos-FRONT-END/tests/product-photos.test.tsx`
- `backend/app/data/assets/product_photographs/sabonete_brisa.png`
- `backend/app/data/assets/product_photographs/shampoo_aurora.png`
- `backend/app/data/assets/product_photographs/hidratante_nuvem.png`
- `backend/app/data/assets/product_photographs/escova_sorriso.png`
- `backend/app/data/assets/product_photographs/algodao_sereno.png`
- `backend/app/data/assets/product_photographs/photos-2026-10.json`
