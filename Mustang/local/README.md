# Mustang/local

Your own files for the Mustang toolbox. Everything in this folder except this README is ignored by git and never committed.

## photos/

Put photos of your own connectors and boxes in `Mustang/local/photos/`. The connector panel looks for, in order:

1. `photos/<connector id>.jpg`, with `:` written as `__`. Example: `ccrm__fuel-pump.jpg` for the `ccrm:fuel-pump` connector.
2. `photos/<part id>.jpg`. Example: `pdb.jpg`.

If neither exists, it shows a committed context photo (engine and engine-bay parts only, see `Mustang/CREDITS.md`) or a plain drawing. A missing file shows up as a 404 in the console. That is normal.

## data.json (optional)

A backup of your pin and slot entries, in the same `mustang-connectors.v1` shape that **Export** writes. The app never reads this file by itself. To load it, open a part's connector panel, then **Edit pin/slot data → Import** and pick the file.
