# paguemenos-FRONT-END

Frontend React + TypeScript + Vite para o MVP Creative Factory. A aplicação oferece catálogo, detalhe do produto, briefing e confirmação da campanha gerada. A consulta detalhada da campanha, validação e revisão serão implementadas nas próximas etapas.

## Execução local

Requer Node.js compatível com as versões fixadas em `package-lock.json`.

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Abra `http://localhost:5173`. Ajuste `VITE_API_BASE_URL` em `.env.local` se o backend estiver em outra URL. O padrão documentado do backend é `http://127.0.0.1:8000`; seu CORS aceita a origem `http://localhost:5173` por padrão. Não coloque segredos em variáveis `VITE_`.

Para subir frontend e backend juntos em contêineres, execute `docker compose up --build -d`
na raiz do projeto. Nesse modo, o frontend usa `/api` via Nginx e o banco SQLite
fica em um volume Docker. Consulte o README da raiz para os comandos completos.

## Verificação

```powershell
npm run lint
npm run test
npm run build
npm run preview
```

O backend está em outro repositório. Veja [contrato da API](docs/API_CONTRACT.md), [arquitetura](docs/FRONTEND_ARCHITECTURE.md) e [progresso](docs/FRONTEND_PROGRESS.md).

