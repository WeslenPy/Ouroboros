import { type RouteConfig, index, layout, route } from "@react-router/dev/routes"

export default [
  layout("layouts/dashboard.tsx", [
    index("routes/overview.tsx"),
    route("politicos", "routes/politicos/list.tsx"),
    route("politicos/:id", "routes/politicos/detail.tsx"),
    route("despesas", "routes/despesas.tsx"),
    route("fornecedores/:documento", "routes/fornecedor.tsx"),
    route("candidaturas", "routes/candidaturas.tsx"),
    route("partidos", "routes/partidos/list.tsx"),
    route("partidos/:sigla", "routes/partidos/detail.tsx"),
    route("entes", "routes/entes/list.tsx"),
    route("entes/:codigo", "routes/entes/detail.tsx"),
    route("fontes", "routes/fontes.tsx"),
    route("matches", "routes/matches.tsx"),
    route("*", "routes/not-found.tsx"),
  ]),
] satisfies RouteConfig
