"""Where a SENTRY may stand (CLAUDE.md 8.27) - the map tools' half of
src/sentry.asm, which promises nothing the level does not.

A sentry's compiled cel steps along a line of video RAM with INC E, so
no line of its box may cross a 256-byte page; and a world character (X,
R) is always at word 40R + X of the ring (8.1), so that is a property of
WHERE IT STANDS and is checked here, once. And it is redrawn only when
it changes, so nothing may be painted under it that it did not save: no
pickup whose cell is repainted when it is taken, no trap cell the
painter is waiting to put down, and no altar or reader whose area moves
on (8.17, 8.23).
"""
import compile_sprite as cs

BOX_W_TILES = 3                 # 12 bytes
BOX_H_TILES = 4                 # 64 lines
GAP = 40                        # tiles between two on one level: a screen
                                # (20) and EN_NEAR either side (16) and a
                                # tile or two - so one she has walked past
                                # is never still NEAR when the next comes
                                # into view, and ENEMY_PICK, which takes
                                # the first near, takes the right one

EK_PICKUP, EK_HAZARD, EK_RECEPTACLE = 4, 5, 7   # src/entity.asm
HZ_MINE = 2                     # src/hazard.asm


def word(x, base_row):
    """Its box's top-left, as a word of the 1024-word ring."""
    top = base_row * 16 - 64
    assert top >= 0 and top % 8 == 0
    return 40 * (top // 8) + 2 * x


def spaced(level, xs):
    """Every enemy of a level GAP tiles from the next, sentries or not."""
    xs = sorted(xs)
    for a, b in zip(xs, xs[1:]):
        assert b - a >= GAP, \
            f"level {level}: enemies at {a} and {b} are near together"


def check(level, sentries, records, w=BOX_W_TILES, h=BOX_H_TILES,
          compiled=True):
    """`sentries` is ((tile column, the row it stands ON), ...);
    `records` the level's entity table as bytes. A COMPILED one must be
    on a column its cel can be drawn on; one the span blitter draws - the
    turret - need not, and is `compiled=False` with its own box."""
    spaced(level, [x for x, _ in sentries])
    recs = [records[i:i + 8] for i in range(0, len(records), 8)]
    for x, row in sentries:
        assert not compiled or cs.page_safe(word(x, row), h * 2, w * 2), \
            f"level {level}: a sentry at tile {x}, row {row} crosses a " \
            f"page of video RAM - its compiled cel cannot be drawn there"
        # ITS BOX IN TILES, and a tile either side of it across
        sx0, sx1, sy0, sy1 = x - 1, x + w, row - h, row - 1
        for r in recs:
            if r[0] not in (EK_PICKUP, EK_RECEPTACLE, EK_HAZARD):
                continue
            rx = (r[1] | r[2] << 8) // 8
            cy = (r[3] | r[4] << 8) // 16 - 1   # the cell its base is under
            if r[0] == EK_PICKUP:
                rect = (rx, rx, cy, cy)
            elif r[0] == EK_HAZARD:             # a column of cells, or a
                wide = 1 if r[6] == HZ_MINE else 0   # mine's 2 x 2 block
                rect = (rx, rx + wide, cy, cy + (r[7] >> 4))
            else:                               # the altar's or the reader's
                rect = (rx - 1, rx + 1, cy - 4, cy)  # 3 x 5 (8.23)
            if (rect[1] >= sx0 and rect[0] <= sx1
                    and rect[3] >= sy0 and rect[2] <= sy1):
                raise AssertionError(
                    f"level {level}: a kind-{r[0]} record at tile {rx}, "
                    f"row {cy} is under the sentry at {x}, {row} - it would "
                    f"be painted over pixels the sentry does not redraw")
