import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const nginxPort = env.NGINX_PORT || "8080";

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      allowedHosts: [".trycloudflare.com"],
      proxy: {
        "/api": {
          target: `http://localhost:${nginxPort}`,
          changeOrigin: true,
        },
      },
    },
  };
})
