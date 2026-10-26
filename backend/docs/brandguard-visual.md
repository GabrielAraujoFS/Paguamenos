# BrandGuard visual determinístico

O endpoint existente `POST /campaigns/{campaign_id}/validate` executa as regras textuais e, para peças com `visual.state == composed`, as verificações visuais. O resultado permanece no `ValidationRun` da peça: `results` contém código, severidade, campo, mensagem e `passed`; `success` exige aprovação de todas as regras críticas. Não há tabela, endpoint ou estado editorial novo.

| Código | Evidência conferida |
|---|---|
| `VISUAL_IMAGE_INTEGRITY` | Referência do arquivo final, ID, tipo, tamanho e SHA-256 contra bytes e sidecar do storage. |
| `VISUAL_PNG_FORMAT`, `VISUAL_DIMENSIONS` | Formato e dimensões lidos por Pillow dos bytes do arquivo, comparados ao canal e à referência. |
| `VISUAL_COMPOSITOR_METADATA` | IDs de peça, produto e fundo registrados pelo compositor contra o JSON da peça. |
| `VISUAL_BACKGROUND_ASSET` | Fundo persistido, SHA-256 e tipo de asset registrado. |
| `VISUAL_TEMPLATE`, `VISUAL_SAFE_AREA`, `VISUAL_OVERLAP` | Template permitido/canônico, caixas registradas, margens e colisões entre áreas obrigatórias. |
| `VISUAL_RENDER_INPUTS` | Produto e textos que o compositor recebeu contra os valores autorizados da peça e do catálogo. É evidência de entrada, **não OCR dos pixels**. |
| `VISUAL_PRODUCT_ASSET`, `VISUAL_LOGO_ASSET`, `VISUAL_FONT_ASSET` | Hashes dos arquivos oficiais atuais contra os hashes capturados na composição. |
| `VISUAL_BRAND_COLORS`, `VISUAL_BRAND_FONT` | Cores declaradas para textos/painéis e fonte declarada, quando a configuração de marca contém permissões. O fundo não é classificado por cor. |
| `HEALTH_CLAIM_REVIEW` | Alerta textual conservador para termos de saúde/eficácia em produtos cuja categoria indica farmácia/medicamento, sem autorização explícita no catálogo. Não substitui revisão regulatória. |

Exemplo reduzido de relatório dentro de `ValidationRun`:

```json
{
  "success": false,
  "results": [
    {"rule_code": "VISUAL_IMAGE_INTEGRITY", "severity": "critical", "field": "visual.final_image", "passed": true, "message": "OK: Arquivo final e SHA-256 conferidos: abcdef012345…"},
    {"rule_code": "VISUAL_LOGO_ASSET", "severity": "critical", "field": "visual.final_image", "passed": false, "message": "Falha: Logotipo usado pelo compositor deve corresponder ao arquivo autorizado atual."}
  ]
}
```

O fingerprint de validação agora inclui os hashes atuais do PNG, sidecars, cópias persistidas de produto e fundo, fotografia oficial, logotipo e fonte. `GET /campaigns/{id}`, `GET /pieces/{id}/image` e a revisão invalidam aprovação antiga quando esses bytes mudam. O histórico permanece auditável. Aprovação exige validação atual bem-sucedida e repetição das verificações antes de registrar a decisão.

Peças textuais antigas sem composição preservam a validação anterior. Peças antigas marcadas como `composed` mas sem a evidência nova precisam ser recompostas antes de uma validação visual conforme. A interface `AdvisoryVisualAnalyzer` reserva uma integração multimodal futura; ela não é chamada nesta etapa.

**Limites:** os hashes detectam mudanças acidentais ou não autorizadas em relação aos metadados locais, mas não constituem assinatura contra um administrador que possa alterar banco e storage conjuntamente. As caixas e textos atestam entradas e layout do compositor; não provam por OCR que cada letra aparece corretamente no PNG. Descontos e validade não possuem campos separados no catálogo atual; são cobertos pelas regras textuais da oferta autorizada, sem inferência de condições comerciais. A conformidade regulatória farmacêutica requer avaliação humana especializada.
