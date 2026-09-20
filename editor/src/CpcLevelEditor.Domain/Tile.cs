namespace CpcLevelEditor.Domain;

/// <summary>
/// One 8×16 tile: its name, what it does, and its pixels in the layout the
/// engine's blitters read.
/// </summary>
/// <remarks>
/// <para>
/// <b>The bytes are COLUMN-MAJOR</b>, which is the ordering all three of
/// <c>DRAW_COLUMN</c>, <c>DRAW_ROW</c> and <c>DRAW_CELL</c> wanted at once
/// (CLAUDE.md 9). Each of the tile's two character columns carries that
/// column's sixteen lines, two bytes each:
/// </para>
/// <code>offset = char_column * 32 + line * 2 + byte</code>
/// <para>
/// Row-major, the source had to step 8 bytes a line; column-major it is one
/// <c>INC L</c> — 64 T a raster instead of 76, for the same 64 bytes in a
/// different order.
/// </para>
/// </remarks>
public sealed class Tile
{
    /// <summary>Mode 0 pixels across.</summary>
    public const int PixelWidth = 8;

    /// <summary>Lines down.</summary>
    public const int PixelHeight = 16;

    /// <summary>Two pixels a byte, so four bytes a line, sixteen lines.</summary>
    public const int ByteCount = PixelWidth / 2 * PixelHeight;

    /// <summary>Mode 0 pixels a CRTC character column.</summary>
    public const int PixelsPerCharColumn = 4;

    public required string Name { get; init; }

    /// <summary>
    /// The 64 bytes, column-major. Held rather than recomputed so a tile
    /// that came off the artist's sheet and a tile the baker made are the
    /// same kind of thing.
    /// </summary>
    public required byte[] Bytes { get; init; }

    /// <summary>What the cell DOES — the byte that goes in the sibling flags file.</summary>
    public TileFlags Flags { get; init; }

    /// <summary>
    /// Whether the artist's <c>tile_table.json</c> calls this one an overlay.
    /// It says how a tile is DRAWN and is independent of <see cref="Flags"/>:
    /// <c>ladder</c> is an overlay in level 3 and opaque in level 1, with the
    /// same <see cref="TileFlags.Ladder"/> in both (CLAUDE.md 8.3).
    /// </summary>
    public bool IsOverlay { get; init; }

    /// <summary>Byte offset of the pixel pair holding <paramref name="x"/>.</summary>
    public static int OffsetOf(int x, int y)
    {
        ArgumentOutOfRangeException.ThrowIfGreaterThanOrEqual((uint)x, (uint)PixelWidth);
        ArgumentOutOfRangeException.ThrowIfGreaterThanOrEqual((uint)y, (uint)PixelHeight);
        var column = x / PixelsPerCharColumn;
        var byteInColumn = x % PixelsPerCharColumn / 2;
        return column * (PixelHeight * 2) + y * 2 + byteInColumn;
    }

    /// <summary>
    /// The pen at a pixel. <b>Pen 0 is transparent in an overlay and opaque
    /// black in anything else</b> — nothing about the pixels says which, only
    /// the table does (CLAUDE.md 7.3).
    /// </summary>
    public byte PenAt(int x, int y)
    {
        var (left, right) = Mode0Layout.Decode(Bytes[OffsetOf(x, y)]);
        return (x & 1) == 0 ? left : right;
    }

    /// <summary>Every pen, as <c>[y][x]</c> — what the baker composites.</summary>
    public byte[][] ToPens()
    {
        var pens = new byte[PixelHeight][];
        for (var y = 0; y < PixelHeight; y++)
        {
            pens[y] = new byte[PixelWidth];
            for (var x = 0; x < PixelWidth; x++)
                pens[y][x] = PenAt(x, y);
        }
        return pens;
    }

    /// <summary>The inverse: pens as <c>[y][x]</c> back into the 64 bytes.</summary>
    public static byte[] Encode(byte[][] pens)
    {
        ArgumentOutOfRangeException.ThrowIfNotEqual(pens.Length, PixelHeight);
        var bytes = new byte[ByteCount];
        for (var y = 0; y < PixelHeight; y++)
        {
            ArgumentOutOfRangeException.ThrowIfNotEqual(pens[y].Length, PixelWidth);
            for (var x = 0; x < PixelWidth; x += 2)
                bytes[OffsetOf(x, y)] = Mode0Layout.Encode(pens[y][x], pens[y][x + 1]);
        }
        return bytes;
    }
}
