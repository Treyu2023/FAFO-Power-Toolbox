# FAFO Auto Tech in the toolbox

Open `Toolbox Launcher.html` and choose Mustang. The tile loads `Mustang/index.html`.

The shop bay source is not edited here. It lives in [FAFO-Auto-Tech](https://github.com/Treyu2023/FAFO-Auto-Tech) under `src/components/auto` and `src/lib/auto`. `Mustang/source/components/auto` and `Mustang/source/lib/auto` are a copy. After a change on either side, run the sync from the Auto Tech repo so the two do not drift:

```
TOOLBOX=/path/to/FAFO-Power-Toolbox node scripts/sync-mustang.mjs
```

That copies the source, the Roush body, and rebuilds `app.js`. Use `--pull` only when the toolbox copy is the one you just edited and Auto Tech should take it.

The body file is `Mustang/models/roush-96-gt.glb`. It is a 1996 Roush GT. The trouble paths are the 2001 shop car.
