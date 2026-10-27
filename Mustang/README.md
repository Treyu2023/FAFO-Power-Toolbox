# FAFO Auto Tech in the toolbox

Open `Toolbox Launcher.html` and choose Mustang, or use the **FAFO Auto Technician** shortcut on the Desktop. Both start the standalone repo at `C:\_Git\repos\html\FAFO-Auto-Tech` (`npm run dev` on port 8080).

The desktop shortcut is a normal Windows shortcut. Right-click it, open Properties, and choose Change Icon. `Change-FAFO-Auto-Tech-Icon.bat` does the same and keeps the icon in `Custom Icons and Theme\Completed ICO\Custom\FAFO-Auto-Tech.ico`.

`Mustang/index.html` is the older bundled page. The launcher does not open it.

The shop bay source is not edited here. It lives in [FAFO-Auto-Tech](https://github.com/Treyu2023/FAFO-Auto-Tech) under `src/components/auto` and `src/lib/auto`. `Mustang/source/components/auto` and `Mustang/source/lib/auto` are a copy. After a change on either side, run the sync from the Auto Tech repo so the two do not drift:

```
TOOLBOX=/path/to/FAFO-Power-Toolbox node scripts/sync-mustang.mjs
```

That copies the source, the Roush body, and rebuilds `app.js`. Use `--pull` only when the toolbox copy is the one you just edited and Auto Tech should take it.

The body file is `Mustang/models/roush-96-gt.glb`. It is a 1996 Roush GT. The trouble paths are the 2001 shop car.
