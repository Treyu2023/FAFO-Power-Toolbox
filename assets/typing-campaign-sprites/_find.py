from pathlib import Path
p = Path(r"C:\_Git\repos\html\HTML Toolbox AI tools\production\Typing Assistant Trainer.html")
t = p.read_text(encoding="utf-8", errors="replace")
keys = [
    "<title>",
    "data-tat-ver",
    'id="tatVer"',
    "var TAT_SPRITE_ROOT",
    "var TAT_NPC_SPRITES",
    "var TAT70_CLASSES",
    "PREF_ALLOW",
    "companionName",
    "Keystroke Chronicles",
    "TYPING ASSISTANT",
    "artTheme",
    "tat85HardRow",
]
for k in keys:
    i = t.find(k)
    print("---", k, "idx", i)
    if i >= 0:
        print(t[i : i + 260].replace("\n", " | "))
