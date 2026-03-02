import { defineConfig, loadEnv, type Plugin } from "vite";

const DEFAULT_BRIDGE_BASE_URL = "http://127.0.0.1:8000";

function stopSentinelOnViteShutdown(bridgeBaseUrl: string): Plugin {
  let shutdownInFlight = false;

  const stopRuntime = async (trigger: string) => {
    if (shutdownInFlight) {
      return;
    }
    shutdownInFlight = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1_200);
    try {
      await fetch(`${bridgeBaseUrl}/api/v1/sentinel/runtime/stop`, {
        method: "POST",
        signal: controller.signal,
      });
    } catch {
      // Best effort only; Vite shutdown should continue.
    } finally {
      clearTimeout(timeout);
      shutdownInFlight = false;
      console.log(`[sentinel-runtime] stop requested on dev-server shutdown (${trigger}).`);
    }
  };

  return {
    name: "sentinel-runtime-stop-on-vite-shutdown",
    configureServer(server) {
      server.httpServer?.once("close", () => {
        void stopRuntime("http_server_close");
      });
    },
  };
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const bridgeBaseUrl = (env.VITE_API_BASE_URL || DEFAULT_BRIDGE_BASE_URL).replace(/\/$/, "");
  const plugins: Plugin[] = [];
  if (command === "serve") {
    plugins.push(stopSentinelOnViteShutdown(bridgeBaseUrl));
  }

  return {
    plugins,
    server: {
      host: "127.0.0.1",
      port: 5173,
    },
  };
});
