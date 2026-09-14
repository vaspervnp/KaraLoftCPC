# CPC hardware palette — firmware ink → hardware colour

Read back from the emulator (`BORDER n`, then sampling the rendered border
colour) rather than transcribed from a table, so it is safe to build the asset
quantiser on.

* **Hardware colour** is the 0–31 value the gate array stores. 27 are distinct.
* **Port value** is what you actually write to `&7Fxx` after selecting a pen:
  `&40 | hardware colour`.
* **Firmware ink** is the number `INK`/`BORDER` use from BASIC. Useful only for
  cross-checking against listings and other people's palettes; the game writes
  the gate array directly and never uses these.

| Ink | Name | HW | Port | RGB |
|---:|---|---:|---|---|
| 0 | Black | 20 | `&54` | 0,2,1 |
| 1 | Blue | 4 | `&44` | 0,2,107 |
| 2 | Bright Blue | 21 | `&55` | 12,2,244 |
| 3 | Red | 28 | `&5C` | 108,2,1 |
| 4 | Magenta | 24 | `&58` | 105,2,104 |
| 5 | Mauve | 29 | `&5D` | 108,2,242 |
| 6 | Bright Red | 12 | `&4C` | 243,5,6 |
| 7 | Purple | 5 | `&45` | 240,2,104 |
| 8 | Bright Magenta | 13 | `&4D` | 243,2,244 |
| 9 | Green | 22 | `&56` | 2,120,1 |
| 10 | Cyan | 6 | `&46` | 0,120,104 |
| 11 | Sky Blue | 23 | `&57` | 12,123,244 |
| 12 | Yellow | 30 | `&5E` | 110,123,1 |
| 13 | White | 0 | `&40` | 110,125,107 |
| 14 | Pastel Blue | 31 | `&5F` | 110,123,246 |
| 15 | Orange | 14 | `&4E` | 243,125,13 |
| 16 | Pink | 7 | `&47` | 243,125,107 |
| 17 | Pastel Magenta | 15 | `&4F` | 250,128,249 |
| 18 | Bright Green | 18 | `&52` | 2,240,1 |
| 19 | Sea Green | 2 | `&42` | 0,243,107 |
| 20 | Bright Cyan | 19 | `&53` | 15,243,242 |
| 21 | Lime | 26 | `&5A` | 113,245,4 |
| 22 | Pastel Green | 25 | `&59` | 113,243,107 |
| 23 | Pastel Cyan | 27 | `&5B` | 113,243,244 |
| 24 | Bright Yellow | 10 | `&4A` | 243,243,13 |
| 25 | Pastel Yellow | 3 | `&43` | 243,243,109 |
| 26 | Bright White | 11 | `&4B` | 255,243,249 |

The 16 pens the game currently uses are in [src/palette.asm](../src/palette.asm).
