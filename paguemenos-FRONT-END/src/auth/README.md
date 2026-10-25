# Autenticação nesta versão

O backend documentado não possui identidade, sessões de usuário, tokens, perfis ou autorização. Todas as sete operações são públicas. Por isso, o cliente HTTP não envia credenciais e as rotas do frontend não têm guardas por perfil. `reviewer_id` é um texto autodeclarado, não uma prova de identidade.

Quando o backend fornecer contratos de autenticação e permissão, projetar a integração aqui antes de criar telas, armazenamento de credenciais ou guardas. Até lá, respostas 401/403 são erros HTTP de infraestrutura, não gatilhos para um login fictício.
