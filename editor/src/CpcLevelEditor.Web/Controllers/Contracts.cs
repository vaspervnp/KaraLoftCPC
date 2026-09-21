using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Web.Controllers;

public sealed record LevelAssets(string Level, IReadOnlyList<string> Sheets);

public sealed record ProjectSummary(
    string Id, string Name, string AssetLevel, string Sheet, int Version);

public sealed record NewProject(
    string Id, string Name, string AssetLevel = "level1_city",
    string Sheet = "city_tiles", string? Seed = null);

public sealed record EntityView(
    EntityKind Kind, ushort X, ushort Y, EntityFlags Flags, byte P0, byte P1);

public sealed record OverlayView(int X, int Y, byte Tile);

public sealed record ProjectView(
    string Id, string Name, string AssetLevel, string Sheet,
    int Width, int Height, int Version, string Map,
    IReadOnlyList<OverlayView> Overlays, IReadOnlyList<EntityView> Entities)
{
    public static ProjectView Of(EditorProject p) => new(
        p.Id, p.Name, p.AssetLevel, p.Sheet, p.Width, p.Height, p.Version,
        Convert.ToBase64String(p.Map),
        [.. p.Overlays.Select(o => new OverlayView(o.X, o.Y, o.Overlay))],
        [.. p.Entities.Select(e => new EntityView(e.Kind, e.X, e.Y, e.Flags, e.P0, e.P1))]);
}

public sealed record TileView(string Name, bool Overlay, byte Flags);

/// <summary>
/// The tileset as the browser draws it.
/// </summary>
/// <remarks>
/// <b>It carries PENS and not Mode 0 bytes, and that is the point.</b> The
/// bit interleaving is written down in exactly two places in this project —
/// <c>tools/cpclib.py</c> and <c>Mode0Layout</c> — and a canvas that
/// unpacked the bytes itself would be a third, in a language with no test
/// suite pointed at it. So the server decodes and the browser draws: two
/// pens to a byte, high nibble first, sixteen lines of eight.
/// </remarks>
public sealed record TilesetView(
    string Level, string Sheet, int TileWidth, int TileHeight,
    IReadOnlyList<int[]> Palette, IReadOnlyList<TileView> Tiles, string Pens);

public sealed record FindingView(string Severity, string Rule, string Message)
{
    public static FindingView Of(Finding f) => new(f.Severity.ToString(), f.Rule, f.Message);
}

public sealed record ExportedFile(string Name, int Length, string Bytes);

public sealed record BakedPairView(int Index, int Over, int Under, string Name, bool Baked);

public sealed record ExportView(
    IReadOnlyList<ExportedFile> Files,
    IReadOnlyList<BakedPairView> Pairs,
    IReadOnlyList<FindingView> Findings,
    string? Directory = null);

/// <summary>One edit. The client sends a batch of them with the version it had.</summary>
public sealed record EditOp(
    string Op, int X = 0, int Y = 0, byte Tile = 0, string? Name = null, byte Flags = 0);

public sealed record EditBatch(int Version, IReadOnlyList<EditOp> Ops);

public sealed record EditResult(int Version, int Applied);
