using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Web.Controllers;

public sealed record LevelAssets(string Level, IReadOnlyList<string> Sheets);

public sealed record ProjectSummary(
    string Id, string Name, string AssetLevel, string Sheet, int Version);

/// <param name="Width">
/// The map's width in tiles; its height follows, because every shape is
/// 2,048 bytes (CLAUDE.md 8.3). 0 means the City's, which is what a
/// horizontal level wants and what the format's own default was.
/// </param>
public sealed record NewProject(
    string Id, string Name, string AssetLevel = "level1_city",
    string Sheet = "city_tiles", string? Seed = null, int Width = 0);

public sealed record EntityView(
    EntityKind Kind, ushort X, ushort Y, EntityFlags Flags, byte P0, byte P1);

public sealed record OverlayView(int X, int Y, byte Tile);

/// <summary>A region in TILES — see <see cref="Region"/> for why tiles.</summary>
public sealed record RegionView(RegionKind Kind, ushort X, ushort Y, byte Width, byte Height);

public sealed record ProjectView(
    string Id, string Name, string AssetLevel, string Sheet,
    int Width, int Height, int Version, string Map,
    IReadOnlyList<OverlayView> Overlays, IReadOnlyList<EntityView> Entities,
    IReadOnlyList<RegionView> Regions)
{
    public static ProjectView Of(EditorProject p) => new(
        p.Id, p.Name, p.AssetLevel, p.Sheet, p.Width, p.Height, p.Version,
        Convert.ToBase64String(p.Map),
        [.. p.Overlays.Select(o => new OverlayView(o.X, o.Y, o.Overlay))],
        [.. p.Entities.Select(e => new EntityView(e.Kind, e.X, e.Y, e.Flags, e.P0, e.P1))],
        [.. p.Regions.Select(r => new RegionView(r.Kind, r.X, r.Y, r.Width, r.Height))]);
}

/// <summary>
/// The enums, by name, so the browser keeps no copy of any of them.
/// </summary>
/// <param name="Lists">
/// Every enum the inspector offers, keyed by the enum's OWN name — which is
/// what lets <see cref="ParamView.Options"/> name one instead of the browser
/// knowing which lists exist. <c>EntityFlags</c> is the four bits of byte 5
/// with <c>None</c> left out; the rest are in declaration order, which for
/// <c>EntityKind</c> and <c>PickupKind</c> is the engine's numbering.
/// </param>
/// <param name="Params">
/// What <c>p0</c> and <c>p1</c> are for, per kind — the table in
/// <see cref="Entity"/>'s remarks and CLAUDE.md 8.6, so an inspector can
/// label two number boxes instead of calling them p0 and p1, and offer a
/// list where the byte is really one of an enum.
/// </param>
/// <param name="DefaultFlags">What a new record of each kind starts as.</param>
/// <param name="Limits">What the engine will take: ENT_MAX and the map's shape.</param>
public sealed record VocabularyView(
    IReadOnlyDictionary<string, IReadOnlyList<string>> Lists,
    IReadOnlyDictionary<string, ParamView[]> Params,
    IReadOnlyDictionary<string, string> DefaultFlags,
    EngineLimitsView Limits)
{
    private const string Pickups = nameof(PickupKind);
    private const string Enemies = nameof(EnemyKind);

    public static VocabularyView Current { get; } = new(
        new Dictionary<string, IReadOnlyList<string>>
        {
            [nameof(EntityKind)] = Enum.GetNames<EntityKind>(),
            [nameof(Domain.EntityFlags)] =
                [.. Enum.GetNames<Domain.EntityFlags>()
                        .Where(n => n != nameof(Domain.EntityFlags.None))],
            [Pickups] = Enum.GetNames<PickupKind>(),
            [Enemies] = Enum.GetNames<EnemyKind>(),
            [nameof(RegionKind)] = Enum.GetNames<RegionKind>(),
        },
        new Dictionary<string, ParamView[]>
        {
            [nameof(EntityKind.Pickup)] =
                [new("which pickup", Pickups), new("amount / lock id / symbol")],
            [nameof(EntityKind.Door)] =
                [new("lock id"), new("which pickup opens it", Pickups)],
            [nameof(EntityKind.Receptacle)] =
                [new("which pickup it takes", Pickups), new("how many it still wants")],
            [nameof(EntityKind.Npc)] = [new("coins asked"), new("which line he says")],
            // p0 IS ALWAYS "WHICH THING THIS IS" (CLAUDE.md 8.6), and the
            // enemy row is the one editor.md had the other way round: the
            // fire rate, the speed, the box and the hit points come from the
            // engine's type table, so a designer places a character — and
            // now picks it off a list, because a number with no list behind
            // it is one ENEMY_ADD can refuse without anybody being told.
            [nameof(EntityKind.Enemy)] =
                [new("which character", Enemies), new("patrol half-width in tiles")],
            [nameof(EntityKind.Hazard)] = [new("damage"), new("period")],
        },
        Enum.GetValues<EntityKind>().ToDictionary(
            k => k.ToString(), k => Entity.DefaultFlagsFor(k).ToString()),
        new EngineLimitsView(EngineLimits.MaxEntities, EngineLimits.MapWidth,
                             EngineLimits.MapHeight, Entity.TileWidth, Entity.TileHeight,
                             [.. EngineLimits.MapShapes
                                             .Select(s => new MapShapeView(s.Width, s.Height))]));
}

/// <summary>
/// One of a kind's two parameter bytes: what to call it, and the enum it is
/// one of when it is one.
/// </summary>
/// <param name="Options">
/// The key in <see cref="VocabularyView.Lists"/> whose index this byte is.
/// Null means it is a plain number.
/// </param>
public sealed record ParamView(string Label, string? Options = null);

/// <param name="MapWidth">
/// The DEFAULT shape, which is the City's. What a project is in is the
/// project's own <c>Width</c> and <c>Height</c> — see <see cref="MapShapes"/>.
/// </param>
/// <param name="MapShapes">
/// Every shape <c>MAP_SHAPE_SET</c> will install, widest first. The engine
/// took one at compile time and takes these at run time (CLAUDE.md 8.3).
/// </param>
public sealed record EngineLimitsView(
    int MaxEntities, int MapWidth, int MapHeight, int TilePixelsWide,
    int TilePixelsTall, IReadOnlyList<MapShapeView> MapShapes);

public sealed record MapShapeView(int Width, int Height);

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

public sealed record EditBatch(int Version, IReadOnlyList<EditOp> Ops);

public sealed record EditResult(int Version, int Applied);

/// <summary>Generate a playable level over whatever this project holds.</summary>
public sealed record GenerateRequest(int Version);

/// <summary>... and what came out, in the words a designer can check.</summary>
public sealed record GeneratedView(
    int Version, int Floors, int Ladders, int Holes, int Pickups, int Enemies,
    string FloorTile, string LadderTile, string BackgroundTile);
