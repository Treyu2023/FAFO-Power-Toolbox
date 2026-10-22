import { spawnSync } from "node:child_process";
import { readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "..");

for (const name of readdirSync(out)) {
  if (name === "app.js" || name.startsWith("part-")) rmSync(path.join(out, name));
}

const css = spawnSync("npx --no-install @tailwindcss/cli -i styles.css -o " + JSON.stringify(path.join(out, "mustang.css")), {
  cwd: here,
  stdio: "inherit",
  shell: true,
});
if (css.status !== 0) process.exit(css.status ?? 1);

await esbuild.build({
  absWorkingDir: here,
  entryPoints: ["entry.tsx"],
  bundle: true,
  format: "esm",
  splitting: true,
  jsx: "automatic",
  outdir: out,
  entryNames: "app",
  chunkNames: "part-[hash]",
  alias: {
    "@/lib/mustang/grok.functions": path.join(here, "grok.stub.ts"),
    "@": here,
  },
});

console.log("Wrote Mustang/index.html bundle into", out);
