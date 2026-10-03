// Sandbox dev: engine on :8000 (real providers when the platform proxy keys exist), production UI bundle on :3000
// via `vite preview` (proxies /v1, /health, /docs, /openapi.json to :8000 — same origin as production).
module.exports = {
  apps: [
    { name: "basira-api", cwd: __dirname, script: "bash", args: "scripts/serve.sh", env: { PORT: 8000 } },
    { name: "basira-ui", cwd: __dirname + "/frontend", script: "npx", args: "vite preview --port 3000 --host 0.0.0.0 --strictPort" },
  ],
};
