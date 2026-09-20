namespace CpcLevelEditor.Domain;

/// <summary>
/// A level as the designer holds it: the map, the entities, and the two
/// sections nothing reads yet. <b>The map's bytes are FINAL tile indices</b>
/// — a cell is a finished tile and nothing is drawn over anything at run
/// time (CLAUDE.md 7.3). Where a designer has dropped a lamp on a wall, the
/// composite that results lives in <see cref="Overlays"/> and is baked into
/// a new tile at export.
/// </summary>
public sealed class Level
{
    /// <summary>Header byte 3.</summary>
    public required byte LevelId { get; init; }

    /// <summary>Header byte 9. Written, never read by the engine.</summary>
    public required byte TilesetId { get; init; }

    /// <summary>Header bytes 5-6, u16 LE. See <see cref="EngineLimits.MapWidth"/>.</summary>
    public required int Width { get; init; }

    /// <summary>Header bytes 7-8, u16 LE.</summary>
    public required int Height { get; init; }

    /// <summary>Flags bits 0-1.</summary>
    public ScrollAxis Scroll { get; init; } = ScrollAxis.Horizontal;

    /// <summary>Flags bit 2.</summary>
    public bool Underwater { get; init; }

    /// <summary>One byte a tile, row-major, <see cref="Width"/> × <see cref="Height"/> of them.</summary>
    public required byte[] Map { get; init; }

    /// <summary>
    /// The live records, and they must be CONTIGUOUS FROM ZERO. The engine
    /// clears its 24 slots and then <c>LDIR</c>s <c>count * 8</c> bytes over
    /// the front, so an inactive record inside that range does not vanish —
    /// it becomes a real entity at whatever coordinates it holds, because
    /// kind 0 is <see cref="EntityKind.PlayerStart"/> and the flags byte is
    /// what decides (CLAUDE.md 8.6).
    /// </summary>
    public IReadOnlyList<Entity> Entities { get; init; } = [];

    public IReadOnlyList<Link> Links { get; init; } = [];

    public IReadOnlyList<Region> Regions { get; init; } = [];

    /// <summary>
    /// The (overlay, background) pairs a designer has placed. This is the
    /// editor's OWN layer and has no home in the file: the format carries
    /// one byte a cell and there is nowhere to say "this cell is an overlay
    /// over that one" (CLAUDE.md 7.3, 8.3). It is resolved at export.
    /// </summary>
    public IReadOnlyList<OverlayPlacement> Overlays { get; init; } = [];

    /// <summary>The map byte at a cell, row-major.</summary>
    public byte this[int x, int y] => Map[y * Width + x];

    /// <summary>
    /// The shape checks every writer of this format makes. Kept off the
    /// exporter so a caller can ask before it has a stream to write to.
    /// </summary>
    public IEnumerable<string> Problems()
    {
        if (Map.Length != Width * Height)
            yield return $"map is {Map.Length} bytes, not {Width}x{Height} = {Width * Height}";

        if (Width != EngineLimits.MapWidth || Height != EngineLimits.MapHeight)
            yield return $"the engine reads {EngineLimits.MapWidth}x{EngineLimits.MapHeight} "
                       + $"and this is {Width}x{Height}: MAP_CELL scales the row out of the "
                       + "base address at compile time, so MAP_INSTALL refuses any other shape";

        if (Entities.Count > EngineLimits.MaxEntities)
            yield return $"{Entities.Count} entities against ENT_MAX = {EngineLimits.MaxEntities}";

        for (var i = 0; i < Entities.Count; i++)
            if (!Entities[i].IsActive)
                yield return $"entity {i} is not EF_ACTIVE, and the engine LDIRs the whole "
                           + "count: an inactive record inside the range becomes a real "
                           + "entity at its own coordinates, not a gap";
    }
}
