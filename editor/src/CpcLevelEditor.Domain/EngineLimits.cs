namespace CpcLevelEditor.Domain;

/// <summary>
/// What the Z80 engine will actually accept, as against what the format can
/// express. These are validation rules, not format rules: the header has a
/// u16 for the width and the engine has three shapes.
/// </summary>
public static class EngineLimits
{
    /// <summary>
    /// <b>The map is 2,048 bytes whatever its shape</b>, and that is a memory
    /// map fact rather than a choice: it sits at <c>MAP_ADDR</c> in base RAM
    /// with the entity table immediately behind it (CLAUDE.md 8.6). So a
    /// shape is ONE number — the width — and the height follows.
    /// </summary>
    public const int MapBytes = 2048;

    /// <summary>
    /// <b>The narrowest map the display can use.</b> 16 tiles is 128 Mode 0
    /// pixels against a 160-pixel screen, so a 16×128 level is 2,048 bytes
    /// and is still refused — by the engine (<c>MAP_SHAPE_SET</c>) and here.
    /// </summary>
    public const int MinMapWidth = 32;

    /// <summary>
    /// <b>The widest, which is the City's.</b> 128×16 is a rooftop: 6.4
    /// screens across and one down.
    /// </summary>
    public const int MaxMapWidth = 128;

    /// <summary>
    /// The shape a new project starts in, and the one every immediate in
    /// <c>src/</c> is written in before <c>MAP_INSTALL</c> patches it.
    /// </summary>
    public const int MapWidth = MaxMapWidth;

    /// <inheritdoc cref="MapWidth"/>
    public const int MapHeight = MapBytes / MapWidth;

    /// <summary>
    /// Every shape the engine takes, widest first: 128×16, 64×32, 32×64.
    /// <para>
    /// <b>THE ENGINE TAKES THESE AT RUN TIME NOW AND IT USED TO TAKE ONE AT
    /// COMPILE TIME.</b> Every mask, shift run and bound that depends on the
    /// width or the height is an immediate patched at <c>MAP_INSTALL</c> out
    /// of the level's own header (<c>src/mapshape.asm</c>), because reading a
    /// shape byte out of memory at each of thirty sites is 7 T against an
    /// immediate's 0 on a frame with 800 T of slack (CLAUDE.md 9).
    /// <c>tools/test_shape.py</c> drives all three on the machine, with the
    /// patcher poked to <c>RET</c> as its control.
    /// </para>
    /// </summary>
    public static IEnumerable<(int Width, int Height)> MapShapes
    {
        get
        {
            for (var w = MaxMapWidth; w >= MinMapWidth; w /= 2)
                yield return (w, MapBytes / w);
        }
    }

    /// <summary>Is this a shape the engine will install?</summary>
    public static bool IsMapShape(int width, int height) =>
        width >= MinMapWidth && width <= MaxMapWidth
        && (width & (width - 1)) == 0
        && (long)width * height == MapBytes;

    /// <summary>
    /// <b>A LEVEL AND AN ENVIRONMENT ARE DIFFERENT THINGS.</b> An environment
    /// is a bank set — the tiles, the characters, the machines — and there are
    /// six of them in <c>assets/sprites/</c>. A level is one map, and several
    /// levels share an environment's art: the art is 16-20 KB and ~1.6 s off
    /// the disc, the map is one sector, so a transition inside an environment
    /// costs nothing a player can see (CLAUDE.md 8.1).
    /// <para>
    /// The level's number is <c>LevelId</c> (header byte 3) and its
    /// environment is <c>TilesetId</c> (byte 9), and the engine reads the
    /// SECOND one to decide whether it has to load art. The numbering is
    /// blocks of <see cref="LevelsPerEnvironment"/>, which is what lets the
    /// two be checked against each other instead of merely coexisting.
    /// </para>
    /// </summary>
    public const int Environments = 6;

    /// <inheritdoc cref="Environments"/>
    public const int LevelsPerEnvironment = 4;

    /// <inheritdoc cref="Environments"/>
    public const int MaxLevels = Environments * LevelsPerEnvironment;

    /// <summary>Which environment a level number belongs to, both 1-based.</summary>
    public static int EnvironmentOf(int levelId) =>
        (levelId - 1) / LevelsPerEnvironment + 1;

    /// <summary>The first level number of an environment, both 1-based.</summary>
    public static int FirstLevelOf(int environment) =>
        (environment - 1) * LevelsPerEnvironment + 1;

    /// <summary>
    /// <c>ENT_MAX</c> — slots in the table the engine clears at install.
    /// A level may carry fewer; it may not carry more.
    /// </summary>
    public const int MaxEntities = 24;

    /// <summary>
    /// The tile index is one byte, so the attribute table the engine clears
    /// and then fills has 256 entries. <c>tileflags_&lt;level&gt;.bin</c> may be
    /// shorter — the loader zeroes the rest — and must not be longer.
    /// </summary>
    public const int TileAttributeCount = 256;

    /// <summary>
    /// Tiles the pickup bake keeps for itself at the top of bank C4
    /// (CLAUDE.md 8.6). A level's own tileset must stop below this, because
    /// <c>ENT_BAKE</c> stamps pickups into indices 240-255 at run time.
    /// </summary>
    public const int ScratchTileFirst = 240;

    /// <summary>
    /// <c>ENT_BAKE_MAX</c> — how many pickups can be drawn at all.
    /// <para>
    /// A pickup is not a sprite: it is composited once into a private copy
    /// of the tile it stands on, and there are sixteen of those copies
    /// (CLAUDE.md 8.6). <c>ENT_BAKE</c> stops when they run out, and
    /// <c>src/entity.asm</c> says what that costs in its own words — "the
    /// rest stay invisible rather than overwrite someone else's art".
    /// </para>
    /// <para>
    /// <b>Invisible is not absent.</b> The AABB never consults the bake, so
    /// the seventeenth pickup is still there to walk into: it goes into her
    /// inventory out of a cell that was drawing plain roof. That is why
    /// this is an error and not a warning — and why <see cref="MaxEntities"/>
    /// is not the limit a level with pickups in it runs into first.
    /// </para>
    /// </summary>
    public const int BakedPickups = 16;

    /// <summary>
    /// Play area in tiles, 20 across by 11 down = 176 lines = 22 character
    /// rows, with the HUD's 16 lines under it making <c>R6 = 24</c>'s 192.
    /// <para>
    /// docs/editor.md 2.1 says the HUD is the 24 bottom lines (176-199) and
    /// therefore a 200-line display; that would be <c>R6 = 25</c>, which
    /// displays 1,000 of the CRTC's 1,024 words and leaves 24 off-screen
    /// where a character row is 40. That margin is what makes vertical
    /// scrolling tear-free (CLAUDE.md 8.2), so the picture is eight lines
    /// shorter than editor.md assumes and those eight are border.
    /// </para>
    /// <para>
    /// What actually ships is smaller still: a 20-cell strip on character row
    /// 23 (CLAUDE.md 7.8), because a band that stays still over a scrolled
    /// picture needs a raster split the frame cannot pay for.
    /// </para>
    /// </summary>
    public const int ScreenTilesAcross = 20;

    /// <inheritdoc cref="ScreenTilesAcross"/>
    public const int ScreenTilesDown = 11;
}
