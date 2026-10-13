import { createContext, useContext, type ReactNode } from "react"

import { api, type OuroborosApi } from "~/provider/api"

const ApiContext = createContext<OuroborosApi>(api)

export function ApiProvider({ children }: { children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
}

export function useApi(): OuroborosApi {
  return useContext(ApiContext)
}
