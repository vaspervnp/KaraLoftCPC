namespace CpcLevelEditor.Exporters;

/// <summary>
/// The constants of docs/editor.md 9.2, in one place so the writer and the
/// reader cannot drift apart.
/// </summary>
public static class LevelFormat
{
    /// <summary>Bytes 0-1. <c>MAP_INSTALL</c> checks these and refuses otherwise.</summary>
    public static ReadOnlySpan<byte> Magic => "LV"u8;

    /// <summary>Byte 2.</summary>
    public const byte Version = 1;

    /// <summary>The header is exactly this long, with no padding after it.</summary>
    public const int HeaderBytes = 21;

    // Flags byte, byte 4. Bits 0-1 are the scroll axis, and SCROLL_H is ZERO.
    public const byte FlagUnderwater = 4;

    /// <summary>
    /// Bit 3 — "the map is RLE". <b>Nothing implements it on either side.</b>
    /// <c>make_level.py</c> defines the constant and has no RLE code path;
    /// the engine never reads the flags byte at all. Writing it would produce
    /// a file that only a future reader could open, so the exporter never
    /// sets it and the reader refuses one that carries it.
    /// </summary>
    public const byte FlagMapIsRle = 8;

    // Header field offsets, for the reader.
    public const int OffVersion = 2;
    public const int OffLevelId = 3;
    public const int OffFlags = 4;
    public const int OffWidth = 5;
    public const int OffHeight = 7;
    public const int OffTilesetId = 9;
    public const int OffEntityCount = 10;
    public const int OffLinkCount = 11;
    public const int OffRegionCount = 12;
    public const int OffSectionOffsets = 13;
}
