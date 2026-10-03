// Serve the actual standalone build. All private APIs are intercepted by QA fixtures.
import { cpSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
const root = new URL("../", import.meta.url);
const standalone = new URL(".next/standalone/", root);
cpSync(new URL(".next/static/", root), new URL(".next/static/", standalone), {
  recursive: true,
});
if (existsSync(new URL("public/", root)))
  cpSync(new URL("public/", root), new URL("public/", standalone), {
    recursive: true,
  });
const child = spawn(
  process.execPath,
  [new URL("server.js", standalone).pathname],
  {
    stdio: "inherit",
    env: {
      ...process.env,
      HOSTNAME: "127.0.0.1",
      PORT: "13030",
      APP_ORIGIN: "http://localhost:13030",
      BACKEND_URL: "http://127.0.0.1:18030",
    },
  },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 0));
