"""Build 3 LetterKey art themes from Kenney CC0 packs already on disk."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "_source"
THEMES = ROOT / "themes"


def copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        print("MISS", src)
        return
    shutil.copy2(src, dest)


def slice_sheet(path: Path, tile: int, out: Path) -> list[Path]:
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    cols, rows = w // tile, h // tile
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    n = 0
    for y in range(rows):
        for x in range(cols):
            cell = im.crop((x * tile, y * tile, (x + 1) * tile, (y + 1) * tile))
            a = cell.getchannel("A")
            if a.getextrema()[1] == 0:
                n += 1
                continue
            fp = out / f"t{n:04d}.png"
            cell.save(fp)
            files.append(fp)
            n += 1
    print(f"sliced {path.name}: {len(files)} nonempty / {cols}x{rows}")
    return files


def pick(files: list[Path], idx: int) -> Path:
    return files[idx % len(files)]


def main() -> None:
    np = SRC / "new-platformer-pack" / "Sprites"
    td = SRC / "tiny-dungeon" / "Tiles"
    abs_p = SRC / "abstract-platformer" / "PNG"
    bit_packed = SRC / "1-bit-pack" / "Tilesheet" / "colored-transparent_packed.png"
    bit_tiles = slice_sheet(bit_packed, 16, SRC / "1-bit-pack" / "sliced")

    # Kenney 1-bit packed layout (16px): letters live near the end.
    # Use last ~40 nonempty-ish by scanning names tXXXX from slice order.
    bit_by_id = {int(p.stem[1:]): p for p in bit_tiles}

    def bit(i: int) -> Path:
        if i in bit_by_id:
            return bit_by_id[i]
        keys = sorted(bit_by_id)
        return bit_by_id[keys[i % len(keys)]]

    # --- TOON (existing Kenney blobs) ---
    toon = THEMES / "toon"
    char = lambda name: np / "Characters" / "Double" / name
    if not (np / "Characters" / "Double" / "character_yellow_front.png").exists():
        char = lambda name: np / "Characters" / "Default" / name
    enem = lambda name: np / "Enemies" / "Double" / name
    if not (np / "Enemies" / "Double" / "frog_idle.png").exists():
        enem = lambda name: np / "Enemies" / "Default" / name
    simp = SRC / "simplified-platformer-pack" / "PNG" / "Characters"

    toon_map = {
        "players/sprinter.png": char("character_yellow_front.png"),
        "players/scholar.png": char("character_beige_front.png"),
        "players/streaker.png": char("character_pink_front.png"),
        "players/guardian.png": simp / "platformChar_idle.png",
        "players/ghost.png": char("character_purple_front.png"),
        "players/zen.png": char("character_green_idle.png"),
        "players/raider.png": enem("slime_spike_rest.png"),
        "players/oracle.png": char("character_beige_idle.png") if (np / "Characters" / "Default" / "character_beige_idle.png").exists() else char("character_beige_front.png"),
        "players/titan.png": simp / "platformChar_happy.png",
        "players/sovereign.png": char("character_yellow_idle.png") if (np / "Characters" / "Default" / "character_yellow_idle.png").exists() else char("character_yellow_front.png"),
        "companion/glyph.png": char("character_green_front.png"),
        "bosses/warden.png": enem("slime_spike_rest.png"),
        "bosses/serpent.png": enem("worm_ring_rest.png"),
        "bosses/sovereign.png": td / "tile_0092.png",
        "npcs/meadow.png": enem("frog_idle.png"),
        "npcs/brook.png": enem("fish_blue_rest.png"),
        "npcs/citadel.png": td / "tile_0088.png",
        "npcs/bridge.png": enem("snail_rest.png"),
        "npcs/mines.png": enem("worm_normal_rest.png"),
        "npcs/village.png": td / "tile_0084.png",
        "npcs/pinky.png": td / "tile_0096.png",
        "npcs/clearing.png": enem("bee_a.png"),
        "npcs/warden.png": enem("slime_spike_rest.png"),
        "npcs/spurroad.png": enem("mouse_walk_a.png") if (np / "Enemies" / "Default" / "mouse_walk_a.png").exists() else enem("mouse_rest.png"),
        "npcs/glyphridge.png": enem("fly_a.png"),
        "npcs/syntaxcreek.png": enem("fish_purple_rest.png") if (np / "Enemies" / "Default" / "fish_purple_rest.png").exists() else enem("fish_blue_rest.png"),
        "npcs/bracketbend.png": enem("snail_shell.png") if (np / "Enemies" / "Default" / "snail_shell.png").exists() else enem("snail_rest.png"),
        "npcs/cascadecause.png": enem("fish_yellow_rest.png") if (np / "Enemies" / "Default" / "fish_yellow_rest.png").exists() else enem("fish_blue_rest.png"),
        "npcs/echohollow.png": enem("frog_jump.png"),
        "npcs/switchyard.png": enem("saw_a.png"),
        "npcs/mistmile.png": enem("fly_b.png") if (np / "Enemies" / "Default" / "fly_b.png").exists() else enem("fly_a.png"),
        "npcs/coilcut.png": enem("worm_ring_rest.png"),
        "npcs/serpentgate.png": enem("slime_block_rest.png"),
        "npcs/serpent.png": enem("worm_ring_rest.png"),
        "npcs/voidthreshold.png": enem("slime_fire_rest.png"),
        "npcs/keystonemarch.png": td / "tile_0085.png",
        "npcs/ciphercloister.png": td / "tile_0090.png",
        "npcs/crowncause.png": td / "tile_0092.png",
        "npcs/obsidianorch.png": enem("bee_b.png") if (np / "Enemies" / "Default" / "bee_b.png").exists() else enem("bee_a.png"),
        "npcs/sigilstairs.png": td / "tile_0086.png",
        "npcs/echothroneroad.png": td / "tile_0087.png",
        "npcs/nightglyph.png": char("character_green_front.png"),
        "npcs/veilofkeys.png": enem("ladybug_rest.png"),
        "npcs/thronewalk.png": simp / "platformChar_walk1.png",
        "npcs/sovereigngate.png": td / "tile_0091.png",
        "npcs/sovereign.png": td / "tile_0092.png",
        "npcs/master.png": td / "tile_0085.png",
        "bg/meadow.png": np / ".." / ".." / "Preview.png" if False else SRC / "new-platformer-pack" / "Preview.png",
    }
    # backgrounds from new-platformer if present
    bg_dir = np / "Backgrounds" / "Default"
    if bg_dir.exists():
        bgs = sorted(bg_dir.glob("*.png"))
        if bgs:
            toon_map["bg/meadow.png"] = bgs[0]
            toon_map["bg/road.png"] = bgs[min(1, len(bgs) - 1)]
            toon_map["bg/throne.png"] = bgs[min(2, len(bgs) - 1)]

    for rel, src in toon_map.items():
        copy(src, toon / rel)

    # --- RUNE (1-bit dungeon + tiny dungeon) ---
    rune = THEMES / "rune"
    # Pick distinctive 1-bit tiles: knights/skulls/letters by scanning nonempty
    ids = sorted(bit_by_id)
    # Heuristic: later tiles include characters, skulls, letters
    rune_map = {
        "players/sprinter.png": bit(ids[len(ids) // 3]),
        "players/scholar.png": bit(ids[len(ids) // 3 + 2]),
        "players/streaker.png": bit(ids[len(ids) // 3 + 4]),
        "players/guardian.png": bit(ids[len(ids) // 3 + 6]),
        "players/ghost.png": bit(ids[len(ids) // 3 + 8]),
        "players/zen.png": bit(ids[len(ids) // 3 + 10]),
        "players/raider.png": bit(ids[len(ids) // 3 + 12]),
        "players/oracle.png": bit(ids[len(ids) // 3 + 14]),
        "players/titan.png": bit(ids[len(ids) // 3 + 16]),
        "players/sovereign.png": bit(ids[len(ids) // 3 + 18]),
        "companion/glyph.png": bit(ids[-8]),
        "bosses/warden.png": bit(ids[len(ids) // 2]),
        "bosses/serpent.png": bit(ids[len(ids) // 2 + 5]),
        "bosses/sovereign.png": bit(ids[len(ids) // 2 + 10]),
        "bg/meadow.png": SRC / "1-bit-pack" / "Sample_fantasy.png",
        "bg/road.png": SRC / "1-bit-pack" / "Sample_interior.png",
        "bg/throne.png": SRC / "1-bit-pack" / "Sample_urban.png",
    }
    # tiny-dungeon character tiles 80-99 as extra class/npc
    dung_chars = [td / f"tile_{i:04d}.png" for i in range(80, 100) if (td / f"tile_{i:04d}.png").exists()]
    class_ids = ["sprinter", "scholar", "streaker", "guardian", "ghost", "zen", "raider", "oracle", "titan", "sovereign"]
    for i, cid in enumerate(class_ids):
        if i < len(dung_chars):
            rune_map[f"players/{cid}.png"] = dung_chars[i]
    if dung_chars:
        rune_map["companion/glyph.png"] = dung_chars[min(5, len(dung_chars) - 1)]
        rune_map["bosses/warden.png"] = dung_chars[min(0, len(dung_chars) - 1)]
        rune_map["bosses/sovereign.png"] = dung_chars[min(len(dung_chars) - 1, 12)]

    nodes = [
        "meadow", "brook", "citadel", "bridge", "mines", "village", "pinky", "clearing", "warden",
        "spurroad", "glyphridge", "syntaxcreek", "bracketbend", "cascadecause", "echohollow",
        "switchyard", "mistmile", "coilcut", "serpentgate", "serpent",
        "voidthreshold", "keystonemarch", "ciphercloister", "crowncause", "obsidianorch",
        "sigilstairs", "echothroneroad", "nightglyph", "veilofkeys", "thronewalk",
        "sovereigngate", "sovereign", "master",
    ]
    dung_all = [td / f"tile_{i:04d}.png" for i in range(0, 132) if (td / f"tile_{i:04d}.png").exists()]
    for i, nid in enumerate(nodes):
        rune_map[f"npcs/{nid}.png"] = dung_all[i % len(dung_all)] if dung_all else bit(ids[i])
    for rel, src in rune_map.items():
        copy(src, rune / rel)

    # --- GLYPH (abstract geometry + keys + 1-bit letters) ---
    glyph = THEMES / "glyph"
    players = {
        "sprinter": abs_p / "Players" / "Player Red" / "playerRed_stand.png",
        "scholar": abs_p / "Players" / "Player Blue" / "playerBlue_stand.png",
        "streaker": abs_p / "Players" / "Player Green" / "playerGreen_stand.png",
        "guardian": abs_p / "Players" / "Player Grey" / "playerGrey_stand.png",
        "ghost": abs_p / "Players" / "Player Blue" / "playerBlue_up1.png",
        "zen": abs_p / "Players" / "Player Green" / "playerGreen_up1.png",
        "raider": abs_p / "Players" / "Player Red" / "playerRed_walk1.png",
        "oracle": abs_p / "Players" / "Player Blue" / "playerBlue_switch1.png",
        "titan": abs_p / "Players" / "Player Grey" / "playerGrey_walk1.png",
        "sovereign": abs_p / "Players" / "Player Green" / "playerGreen_switch1.png",
    }
    glyph_map = {f"players/{k}.png": v for k, v in players.items()}
    glyph_map.update({
        "companion/glyph.png": abs_p / "Items" / "keyGreen.png",
        "bosses/warden.png": abs_p / "Enemies" / "enemySpikey_1.png",
        "bosses/serpent.png": abs_p / "Enemies" / "enemySwimming_1.png",
        "bosses/sovereign.png": abs_p / "Items" / "keyRed.png",
        "bg/meadow.png": abs_p / "Backgrounds" / "set1_background.png",
        "bg/road.png": abs_p / "Backgrounds" / "set2_background.png",
        "bg/throne.png": abs_p / "Backgrounds" / "set3_background.png",
    })
    enemies = [
        abs_p / "Enemies" / "enemyWalking_1.png",
        abs_p / "Enemies" / "enemyWalking_2.png",
        abs_p / "Enemies" / "enemyFlying_1.png",
        abs_p / "Enemies" / "enemyFlying_2.png",
        abs_p / "Enemies" / "enemyFloating_1.png",
        abs_p / "Enemies" / "enemyFloating_2.png",
        abs_p / "Enemies" / "enemySpikey_2.png",
        abs_p / "Enemies" / "enemySwimming_2.png",
        abs_p / "Enemies" / "enemyWalking_3.png",
        abs_p / "Enemies" / "enemyFlying_3.png",
        abs_p / "Items" / "outlineKey.png",
        abs_p / "Items" / "blueGem.png",
        abs_p / "Items" / "greenCrystal.png",
        abs_p / "Items" / "yellowJewel.png",
        abs_p / "Items" / "puzzleGreen.png",
        abs_p / "Other" / "blockGreen_key.png",
        abs_p / "Other" / "blockGreen_lock.png",
        abs_p / "Items" / "redGem.png",
        abs_p / "Items" / "discGreen.png",
        abs_p / "Items" / "outlineCrystal.png",
    ]
    for i, nid in enumerate(nodes):
        glyph_map[f"npcs/{nid}.png"] = enemies[i % len(enemies)]
    for rel, src in glyph_map.items():
        copy(src, glyph / rel)

    # Extract 1-bit A-Z if we can find a row of 26 similar letter tiles at the end
    letter_dir = glyph / "letters"
    letter_dir.mkdir(parents=True, exist_ok=True)
    # Copy last 36 nonempty tiles as digits+letters fallback
    tail = [bit_by_id[k] for k in sorted(bit_by_id)[-40:]]
    for i, p in enumerate(tail):
        copy(p, letter_dir / f"g{i:02d}.png")

    print("themes ready")
    for t in ("toon", "rune", "glyph"):
        n = len(list((THEMES / t).rglob("*.png")))
        print(f"  {t}: {n} pngs")


if __name__ == "__main__":
    main()
