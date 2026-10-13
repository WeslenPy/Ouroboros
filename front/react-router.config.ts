import type { Config } from "@react-router/dev/config";

export default {
  // SPA: sem auth, nada para renderizar no servidor. Build estático servido pelo nginx.
  ssr: false,
} satisfies Config;
