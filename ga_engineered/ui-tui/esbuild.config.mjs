import esbuild from "esbuild";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const outdir = resolve(here, "dist");

await mkdir(outdir, { recursive: true });

// Ink imports ``react-devtools-core`` from a dynamic ``./devtools.js`` that
// is only loaded when ``process.env.DEV`` is set, but esbuild's bundler
// hoists the dynamic import into a static one and the package then has to
// be present at runtime. Stubbing the import with a no-op keeps the bundle
// self-contained while still letting Ink's devtools branch fail silently
// if anyone ever tries to enable it on a production install.
const devtoolsStubPlugin = {
  name: "react-devtools-stub",
  setup(build) {
    build.onResolve({ filter: /^react-devtools-core$/ }, (args) => ({
      path: args.path,
      namespace: "devtools-stub",
    }));
    build.onLoad({ filter: /.*/, namespace: "devtools-stub" }, () => ({
      contents:
        "const noop = () => {};\nexport default { initialize: noop, connectToDevTools: noop };\n",
      loader: "js",
    }));
  },
};

await esbuild.build({
  entryPoints: [resolve(here, "src/entry.tsx")],
  bundle: true,
  outfile: resolve(outdir, "bundle.js"),
  platform: "node",
  format: "esm",
  target: "node20",
  jsx: "automatic",
  banner: {
    // Ink + React on Node ESM need a shim for require() of CJS deps.
    js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);",
  },
  plugins: [devtoolsStubPlugin],
  minify: false,
  sourcemap: false,
  logLevel: "info",
});
