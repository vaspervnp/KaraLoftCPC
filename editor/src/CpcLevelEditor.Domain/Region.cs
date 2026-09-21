namespace CpcLevelEditor.Domain;

/// <summary>Seven bytes: kind, x u16, y u16, w, h (docs/editor.md 9.2).</summary>
/// <remarks>
/// <para>
/// Seven, not eight — there is no padding anywhere in this format, and the
/// header's region count is <c>length / 7</c>. An exporter that aligned the
/// record to eight would report a count that is nearly right and a section
/// that is not.
/// </para>
/// <para>
/// <b>AND THE UNIT IS TILES, WHICH THE FIELD WIDTHS SETTLE.</b> An entity is
/// placed in world PIXELS because a designer drops it on a floor line
/// (<see cref="Entity"/>); a region's width and height are single BYTES, and
/// 255 pixels is 31 tiles of a 128-tile map — a region that could not span a
/// level is not a region. docs/editor.md 5.5 says tiles as well
/// («ορθογώνια σε tiles»), and nothing in the engine reads one yet, so this
/// is where it is written down.
/// </para>
/// </remarks>
public readonly record struct Region(RegionKind Kind, ushort X, ushort Y, byte Width, byte Height)
{
    public const int Stride = 7;

    /// <summary>Pixels across a tile, for anything that has to draw one.</summary>
    public const int TileWidth = Entity.TileWidth;

    /// <summary>Pixels down a tile.</summary>
    public const int TileHeight = Entity.TileHeight;
}
