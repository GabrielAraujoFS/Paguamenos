# Instruções permanentes para desenvolvimento do frontend

## Fonte de verdade e escopo

- Antes de alterar fluxos, leia `docs/API_CONTRACT.md`, `docs/FRONTEND_HANDOFF.md`, `docs/FRONTEND_IMPLEMENTATION_PLAN.md` e `docs/openapi.json`. Consulte `docs/FRONTEND_ARCHITECTURE.md`, `docs/FRONTEND_ROADMAP.md` e `docs/FRONTEND_PROGRESS.md` para decisões e estado do frontend.
- Use somente contratos reais documentados. Confirme divergências relevantes com o OpenAPI vivo e o comportamento do backend quando ele estiver acessível; registre a divergência antes de adaptar o cliente. Não invente endpoints, campos, autenticação, papéis nem permissões.
- O backend está em outro repositório. Não o altere a partir deste projeto. Se uma função depender de API ausente, documente o bloqueio e não apresente uma simulação como integração real.
- Preserve arquivos existentes e alterações do usuário. Mantenha este planejamento até haver instrução para implementar funcionalidades.

## Organização e qualidade

- Organize o código por funcionalidade. Separe páginas e layouts, componentes de interface, hooks de consulta e mutação, serviços HTTP, tipos de contrato, autenticação/permissões quando houver contrato, utilitários e configuração.
- Centralize cliente Axios, URL-base, normalização de erros, chaves de cache e chamadas de API. Evite duplicar lógica, tipos, validações e componentes. Extraia componentes reutilizáveis quando houver uso real, sem abstrações prematuras.
- Use TypeScript rigoroso (`strict`), tipos explícitos nos limites da API e sem `any` injustificado. Mantenha IDs opacos, datas como ISO UTC e preços como strings decimais; não use aritmética binária para valores comerciais.
- Use React Hook Form e Zod apenas para regras de entrada documentadas. A validação de marca e as transições de estado pertencem ao backend; a resposta atual da API prevalece sobre o estado local.
- Não introduza dados fictícios como substitutos de integrações reais. Fixtures são permitidas somente em testes, identificadas como tais. Não coloque segredos ou chave do provedor de geração no bundle.
- Não implemente login, guardas de rota por perfil ou cabeçalho `Authorization` enquanto o backend não fornecer contrato de identidade e autorização. `reviewer_id` é autodeclarado.

## Verificação e registro

- Teste mudanças proporcionais ao risco: tipagem/build, lógica de formulários e cache, estados de erro e fluxos integrados com a API real ou respostas de teste fiéis ao contrato. Evite testes que apenas reproduzem a implementação.
- Em mutações que criam histórico (`validate` e `review`), impeça envio duplicado acidental e não configure repetição automática. Trate `409`, `422`, `502`, `404` e falhas de rede conforme o contrato.
- Ao concluir uma etapa, atualize `docs/FRONTEND_PROGRESS.md` com o que foi implementado, como foi testado, resultado e pendências. Atualize arquitetura e roadmap se uma decisão mudar; registre lacunas da API sem disfarçá-las.
