using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

/// <summary>
/// A level as the DESIGNER holds it, which is not the level the engine
/// reads.
/// </summary>
/// <remarks>
/// <para>
/// <b>The map here carries the ARTIST's tile indices and the overlays are a
/// layer of their own.</b> The engine's map cell is a finished tile and
/// nothing is drawn over anything at run time (CLAUDE.md 7.3), so the
/// pairing has to live somewhere the format has no room for — and this is
/// that somewhere. Export composites it away; nothing about the engine
/// changes.
/// </para>
/// <para>
/// <b>And the tile flags are keyed by NAME, not by index.</b> A tile's index
/// is the artist's frame order and a re-exported sheet can renumber it; what
/// a cell DOES belongs to the thing, not to its place in a sheet. The
/// exporter resolves names to indices at the last moment.
/// </para>
/// </remarks>
public sealed class EditorProject
{
    /// <summary>The slug it is stored and addressed under.</summary>
    public required string Id { get; init; }

    public required string Name { get; set; }

    /// <summary>Which level's art package this paints out of, e.g. <c>level1_city</c>.</summary>
    public required string AssetLevel { get; init; }

    /// <summary>Which tile sheet of it, for the levels that have more than one.</summary>
    public required string Sheet { get; init; }

    public byte LevelId { get; set; } = 1;

    public byte TilesetId { get; set; } = 1;

    public ScrollAxis Scroll { get; set; } = ScrollAxis.Horizontal;

    public bool Underwater { get; set; }

    /// <summary>128 x 16 artist tile indices, row-major.</summary>
    public required byte[] Map { get; init; }

    public List<OverlayPlacement> Overlays { get; init; } = [];

    public List<Entity> Entities { get; init; } = [];

    public List<Link> Links { get; init; } = [];

    public List<Region> Regions { get; init; } = [];

    /// <summary>What each named tile DOES — the editor's own data (CLAUDE.md 11 step 7).</summary>
    public Dictionary<string, TileFlags> TileFlags { get; init; } = [];

    /// <summary>
    /// Bumped on every accepted change. It is the ETag a client sends back,
    /// so two browsers on one project cannot silently overwrite each other.
    /// </summary>
    public int Version { get; set; }

    public int Width => EngineLimits.MapWidth;

    public int Height => EngineLimits.MapHeight;

    /// <summary>
    /// <b>The art package's directory name carries the level's number</b> —
    /// <c>level2_forest</c> is level 2 — and that number is byte 3 of the
    /// file and the name it exports under. A new project that took the
    /// default would write level 2 out as <c>level_1.lvl</c>, over the City.
    /// </summary>
    public static byte LevelIdFor(string assetLevel)
    {
        var digits = new string([.. assetLevel
            .SkipWhile(c => !char.IsAsciiDigit(c))
            .TakeWhile(char.IsAsciiDigit)]);
        return byte.TryParse(digits, out var id) && id > 0 ? id : (byte)1;
    }

    /// <summary>The level in the shape the exporters take, overlays and all.</summary>
    public Level ToLevel() => new()
    {
        LevelId = LevelId,
        TilesetId = TilesetId,
        Width = Width,
        Height = Height,
        Scroll = Scroll,
        Underwater = Underwater,
        Map = (byte[])Map.Clone(),
        Entities = [.. Entities],
        Links = [.. Links],
        Regions = [.. Regions],
        Overlays = [.. Overlays],
    };
}
