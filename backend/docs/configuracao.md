# Configuração sintética de marca e campanha

O arquivo `app/data/brand_rules.json` reúne as configurações locais. Ele não é
um cadastro de marcas e não há endpoint administrativo. Nome, identidade, cores,
regras e ofertas de exemplo são fictícios; nenhuma marca real é definitiva.

O arquivo é validado por `app/schemas/configuration.py` na criação da aplicação
e em cada leitura. Campos desconhecidos, severidades indevidas, cores inválidas,
modelos com placeholders desconhecidos ou limites incompletos causam erro de
configuração. Corrija o arquivo antes de servir requisições; alterações inválidas
durante a execução não são ignoradas nem substituídas por regras permissivas.

## Perfil e geração mock

- `brand.name`: nome textual; disponível nos modelos como `{brand_name}`.
- `brand.textual_identity`: frase da identidade, disponível como `{brand_identity}`.
- `brand.allowed_colors`: lista de cores hexadecimais `#RRGGBB`, apenas referência.
  Não existem imagens ou campos de cor nas peças; nada é validado visualmente.
- `brand.tone_of_voice`: estilo determinístico `neutro`, `acolhedor` ou `direto`.
  O mock usa respectivamente os CTAs “Conheça o produto”, “Conheça com calma” e
  “Confira agora”. Um template de CTA literal substitui essa escolha. Não há
  julgamento semântico do tom; novos estilos exigem implementação explícita.
- `generation.disclaimer`: aviso anexado pelo backend, fora da saída do provedor.
- `generation.templates`: modelos de `title`, `subtitle` e `cta` por canal.
  Configure `feed`, `story` e `banner`. Placeholders aceitos: `{product_name}`,
  `{description}`, `{brand_name}`, `{brand_identity}` e `{cta}`. Não há acesso a
  preço/oferta nem a atributos Python. Use `{{` e `}}` para chaves literais.

O mock não interpreta livremente objetivo, público ou instruções; mantém esses
dados no briefing. Não adiciona automaticamente cada expressão obrigatória nem
trunca textos para fazê-los passar. O Guardian aponta incompatibilidades entre
os modelos e as regras, inclusive excesso de caracteres. Tudo continua local,
sem chaves ou serviços externos. `GET /health` identifica `generation_provider: mock`.

## Verificações e severidade

Permanecem críticos e não podem ser rebaixados pela configuração:

- `PRODUCT_EXISTS`, `PRICE_MATCH`, `PRODUCT_NAME_MATCH`, `OFFER_MATCH`;
- `REQUIRED_FIELD` para os campos do contrato, mesmo se `required_fields` for reduzido;
- `CHANNEL_ALLOWED`, `TEXT_PRICE_MATCH` e `TEXT_OFFER_MATCH`.

`allowed_channels` define os canais admitidos pelo Guardian. A entrada da API
continua aceitando os três enums originais; um canal desabilitado na configuração
gera peça `draft`, com falha crítica ao validar. `required_fields` permite declarar
explicitamente os campos obrigatórios conhecidos. `character_limits` exige limites
positivos de título, subtítulo e CTA para cada canal; pode incluir o disclaimer.

`severities` permite escolher `critical`, `warning` ou `info` somente para
`CHARACTER_LIMIT` e `REQUIRED_INFORMATION`; a ausência mantém `critical`.
`required_information` preserva o formato anterior: campo → lista de expressões,
todas exigidas naquele campo.

`required_expressions` e `forbidden_expressions` contêm objetos como:

```json
{
  "expression": "Confira os detalhes",
  "fields": ["subtitle", "cta"],
  "channels": ["feed"],
  "severity": "warning"
}
```

O mesmo objeto pode ser usado em uma das duas listas. `expression` é obrigatório;
os padrões dos demais campos são: todos os campos textuais, todos os canais e
severidade crítica. Campos textuais admitidos: `title`, `subtitle`, `cta`, `disclaimer`.

- Obrigatória: deve aparecer em pelo menos um dos campos indicados. Resultado
  `REQUIRED_EXPRESSION`; `field` lista os candidatos separados por vírgula.
- Proibida: é verificada em cada campo indicado. Resultado `FORBIDDEN_EXPRESSION`
  com o campo específico. As expressões fornecidas são exemplos sintéticos,
  não um catálogo completo de alegações clínicas, legais ou de marca.
- A comparação ignora maiúsculas, acentos e espaços repetidos, com limites de
  palavra. “cura” não corresponde a “procura”. Pontuação é preservada: não há
  detecção de paráfrases, sinônimos ou tentativas arbitrárias de ofuscação.

`passed: false` indica a falha da regra. Uma falha `warning` ou `info` não impede
`success: true` na execução e não bloqueia revisão humana. Uma falha `critical`
mantém a peça em `draft` e impede aprovação. A validação nunca aprova sozinha.

## Preços e condições comerciais

O catálogo continua sendo a fonte de preço e da string `authorized_offer`. Não
foi criado cálculo de descontos nem um modelo de condições comerciais estruturadas:
hoje as condições autorizadas estão nessa string. Preços estruturados usam Decimal,
e nome/oferta estruturados precisam reproduzir o catálogo.

Nos campos textuais, a verificação tem escopo deliberadamente limitado:

- `commercial.text_price_policy: catalog_only`: valores no formato brasileiro
  `R$ 8,90` ou `R$ 1.234,56` precisam ser iguais ao preço unitário do catálogo.
  A comparação usa Decimal. Valores múltiplos são verificados individualmente.
- `forbid`: nenhum preço reconhecido pode aparecer no texto, nem dentro de uma
  cópia da oferta autorizada. O campo estruturado `price` continua presente.
- `R$` malformado, notações com `reais`, `BRL`, `$`, `€` e `£` são sinalizadas
  como não verificáveis nesta implementação. Não há conversão de moedas.
- Percentuais numéricos (`10%`), construções numéricas “leve 2”, “pague 1”, “2 por”
  e os termos de `commercial.offer_markers` exigem a reprodução da oferta
  completa autorizada no mesmo campo. Os marcadores são configuráveis; a
  detecção das construções numéricas permanece ativa.
- Uma cópia completa da oferta do catálogo, normalizada como as expressões,
  autoriza somente os valores e condições desse trecho. Acrescentar outra oferta
  ou outro preço reconhecido continua sendo verificado. Não combine ou recalcule
  ofertas. Se mudar `authorized_offer`, as validações antigas perdem a validade.

Essas são verificações sintáticas conservadoras: podem gerar falsos positivos
(por exemplo, “sem desconto”) e não entendem todas as formas de anunciar preço,
condições por extenso ou benefícios. Um texto sem falhas não tem conformidade
semântica, clínica ou jurídica garantida. A revisão humana é obrigatória.

## Compatibilidade, histórico e demonstração

Os sete endpoints, schemas públicos, estados, códigos HTTP e formato monetário
continuam iguais. Novos códigos de regra aparecem nas listas de resultados.
`brand` e `generation` são configuração do servidor, não novos campos do briefing.
As cores não são expostas na API. Múltiplos públicos não foram implementados.

O SQLite não precisa de migração: validações e decisões usam as tabelas existentes.
A assinatura inclui o conteúdo, produto e configuração completa normalizada.
**Ao atualizar para esta versão, validações anteriores podem ficar desatualizadas**,
inclusive pela inclusão de novos padrões de configuração. Consulte e revalide a
campanha antes de revisar. A peça volta a `draft` se a assinatura divergir; os
registros de validações e decisões anteriores permanecem no histórico.

Os resultados e assinaturas são guardados, mas não há snapshot integral das
versões antigas do arquivo de configuração nem histórico completo de edição.

Veja [exemplos de alerta e bloqueio](../examples/configurable_validation.json).
`configuration_overrides` nesses exemplos descreve alterações locais no JSON;
**não é corpo de requisição da API**. Para demonstrar:

1. Use uma cópia de desenvolvimento e banco isolado, sem editar a configuração
   enquanto outra pessoa estiver demonstrando o mesmo processo.
2. Adicione uma expressão recomendada ausente em `required_expressions`, com
   severidade `warning`, e gere/valide uma campanha. Há alerta, mas a peça fica
   `validated`; a aprovação ainda exige ação explícita do revisor.
3. Para um bloqueio sintético, coloque “cura garantida” no modelo de título de
   `feed`. Gere outra campanha e valide: a expressão proibida bloqueia a aprovação
   com 409. Restaure o template depois da demonstração.

## Futuro provedor de IA

A interface continua `generate(briefing, product) -> list[GeneratedText]`.
Implemente-a e injete uma instância em `create_app(generator=SeuProvedor())`.
O provedor deve devolver apenas canal, título, subtítulo e CTA, exatamente uma
peça por canal pedido. O schema rejeita campos comerciais extras; resposta
malformada ou canais inconsistentes retornam erro estruturado 502.

Nome, preço, oferta e aviso são anexados pelo backend. As regras devem ser
aplicadas ao texto de qualquer provedor. Antes da integração real, definir
timeout, tratamento de falhas, dados permitidos e gestão de credenciais.
Os atuais templates não produzem conteúdo de IA real.
