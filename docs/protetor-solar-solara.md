# Protetor Solar Solara — inclusão no catálogo

Produto inteiramente fictício, sem associação com produtos reais da Pague Menos.

- Identificador: `syn-006`.
- Nome: Protetor Solar Solara.
- Categoria: Proteção solar.
- Descrição autorizada: Protetor solar facial fictício FPS 50, toque seco, 60 g.
- Preço: R$ 39,90 (`39.90` na API).
- Oferta: Preço sintético de demonstração, sem desconto adicional.

## Fotografia e compatibilidade

O arquivo fornecido foi encontrado em `assets/produtos/protetor_solar_solara.png.png`, com extensão duplicada. É um PNG RGB íntegro de 1536 × 1024 pixels. O original foi preservado; uma cópia byte a byte foi incluída no armazenamento existente do backend como `protetor_solar_solara.png`.

SHA-256: `906453e9c2fdb085183ddec26d751e7bf893ecc9936b85d5258bb3e34d6aa484`.

O registro `photos-2026-10.json` associa o identificador à fotografia e ao hash. O compositor existente preserva o fundo e a proporção da fotografia; o Brand Guardian confere a associação, a integridade e os metadados. Não houve alteração em regras, modelos de geração, contratos, campanhas persistidas ou fotografias anteriores.

O rótulo da fotografia contém também “UVA + UVB” e “controle de oleosidade”. Essas expressões não foram adicionadas ao catálogo nem autorizadas para novos textos. A fotografia foi preservada conforme solicitada; a validação visual existente não equivale a uma revisão semântica por OCR de todo o rótulo.

## Atualização do Docker

Na raiz do projeto:

```powershell
docker compose build backend frontend
docker compose up -d backend frontend
```

Os volumes existentes devem ser mantidos. Não é necessário alterar Compose ou credenciais.

## Roteiro manual

1. Abrir `http://localhost:5173/products`, confirmar os seis produtos e a fotografia do Solara.
2. Abrir seus detalhes e conferir categoria, descrição, R$ 39,90 e oferta.
3. Criar briefing a partir do produto; selecionar tema e estilo existentes.
4. Gerar uma campanha com preço oculto e outra com preço exibido. Conferir a identificação de conteúdo demonstrativo caso o usuário escolha essa alternativa.
5. Compor a peça, conferir a fotografia completa e baixar o PNG. Se o provedor estiver indisponível, escolher explicitamente a composição local.
6. Validar no Brand Guardian, conferir os resultados e aprovar/rejeitar manualmente com identificação do revisor.
7. Reabrir campanhas antigas e conferir imagens, histórico e aprovações preservados.
8. Consultar `/api/products`, `/api/products/syn-006` e `/api/products/syn-006/image` no frontend; os mesmos caminhos sem `/api` estão disponíveis diretamente na porta 8000.

Testes automatizados usam provedores simulados e dados temporários, sem chamadas reais às APIs de IA.

## Verificação executada

- Suíte completa do backend: 321 testes aprovados, 8 avisos preexistentes (Starlette/httpx e serialização de enums em fixtures).
- Rodada posterior específica de fotografias: 38 testes aprovados, incluindo o teste adicional de preservação integral dos cinco registros anteriores. Os totais se sobrepõem e não devem ser somados.
- Frontend: 49 testes aprovados, 1 ignorado; TypeScript, ESLint e build de produção aprovados.
- Construção das imagens Docker de backend e frontend aprovada.
- Proxy real Nginx /api: listagem de seis produtos, detalhes syn-006 e fotografia íntegra conferidos.
- Duas campanhas no Docker, com preço oculto/exibido, tema e estilo: geração mock identificada, falha visual com provedor desabilitado, escolha explícita de recursos locais, composição, Brand Guardian, aprovação humana e download PNG aprovados.
- Ambiente Docker separado, SQLite em memória e armazenamento temporário, sem volumes ou credenciais de IA. Um 502 inicial ocorreu antes do backend concluir a inicialização; após a inicialização, o fluxo passou integralmente.
- Não houve teste de geração paga por Gemini nem revisão manual do navegador nesta etapa. O roteiro acima orienta a conferência visual após atualizar os serviços reais.
