# Ouroboros — front

Dashboard somente leitura sobre a API (`back/`). Mesma stack do WADashboard, sem auth:
React 19 + React Router 7 (modo SPA, `ssr: false`), Vite 6, Tailwind v4, shadcn/ui (new-york),
TanStack Table, Recharts, i18next (pt/en), sonner.

## Rodar

```sh
cp .env.example .env      # VITE_API_URL=http://localhost:8000
npm install
npm run dev               # http://localhost:5173
npm run typecheck
npm run build             # estático em build/client
```

Docker: `docker compose up --build front` na raiz (nginx servindo `build/client`, porta 5173).
`VITE_API_URL` é embutida no build (build-arg), então aponta para a API como o navegador a vê.

## Estrutura

- `app/routes.ts` — rotas; páginas em `app/routes/`
- `app/provider/api.ts` — cliente da API (`OuroborosApi`), export CSV
- `app/interface/api.ts` — tipos espelhando `back/src/ouroboros/api/schemas.py`
- `app/hooks/use-resource.ts` — `useResource` (busca + polling) e `useCursorList` (paginação por cursor)
- `app/hooks/use-filters.ts` — filtros na query string
- `app/components/ui/` — shadcn (copiado do WADashboard); `custom/` e `charts/` — componentes do app
- `app/i18n/` — traduções pt/en
