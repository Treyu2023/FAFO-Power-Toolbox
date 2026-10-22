# 2001 Mustang shop tool

The page you open from the toolbox is [index.html](index.html). It is already built. No install is required to use it.

The files you edit are in [source](source). This sandbox copy was not its own git repo. The source and the built page both live in this repo:

https://github.com/Treyu2023/FAFO-Power-Toolbox

Open `Toolbox Launcher.html` (or `Phone Launcher.html`) and choose Mustang. The tile loads `Mustang/index.html`.

## Rebuild after you change the source

From `Mustang/source`, with Node installed:

```
npm install
npm run build
```

That rewrites `../mustang.css`, `../app.js`, and the `part-*.js` chunks. Commit those with your source changes or the launcher will still be on the old bundle.

`source/grok.stub.ts` is what the toolbox build calls. It does not send symptoms anywhere. `source/lib/mustang/grok.functions.ts` is the online-bay version and is not wired into this static build.

Wheel zooms. Shift+wheel opens the car. Right-click a part to hide it or start the fuel-pump power walkthrough.
