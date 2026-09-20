namespace CpcLevelEditor.Domain;

/// <summary>
/// What the Z80 engine will actually accept, as against what the format can
/// express. These are validation rules, not format rules: the header has a
/// u16 for the width and the engine has one shape.
/// </summary>
public static class EngineLimits
{
    /// <summary>
    /// <b>The map is 128×16 tiles or <c>MAP_INSTALL</c> refuses it</b>, because
    /// <c>MAP_CELL</c> scales the row out of the base address at compile time
    /// (CLAUDE.md 8.3). <c>tools/test_format.py</c> carries this as a negative
    /// control: poke the width to 64 and the loader leaves <c>MAP_ADDR</c>
    /// zeroed.
    /// <para>
    /// docs/editor.md 5.2 models a level as 20×screens by 11×screens, which is
    /// the play area tiled out; that is a different thing from what the engine
    /// indexes, and CLAUDE.md wins.
    /// </para>
    /// </summary>
    public const int MapWidth = 128;

    /// <inheritdoc cref="MapWidth"/>
    public const int MapHeight = 16;

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
