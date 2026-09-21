using System.Text.Json;
using System.Text.Json.Serialization;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

/// <summary>
/// A project on disk, as JSON.
/// </summary>
/// <remarks>
/// <b>A LEVEL IS SOURCE, SO ITS STORE IS A FILE AND NOT A DATABASE.</b>
/// docs/editor.md 6.3 makes SQLite the default and names this as the
/// alternative — "easy to git diff, but no concurrency and no queries" — and
/// for this project the trade goes the other way: the editor's whole output
/// is files that the build reads and the repository versions, there is one
/// designer, and a database would add migrations, a connection string and an
/// Identity stack to a tool whose correctness is entirely in its bytes. The
/// store is behind <see cref="IProjectStore"/>, so a team that wants rows
/// can have them without touching anything above it.
/// <para>
/// The map travels as base64 because 2,048 numbers in JSON is 8 KB of commas
/// and unreadable either way; everything a person might want to edit by hand
/// — the entities, the tile flags, the overlay layer — is spelled out.
/// </para>
/// </remarks>
public static class ProjectJson
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingDefault,
        Converters = { new JsonStringEnumConverter() },
    };

    public static string Write(EditorProject project) =>
        JsonSerializer.Serialize(Document.Of(project), Options);

    public static EditorProject Read(string json) =>
        (JsonSerializer.Deserialize<Document>(json, Options)
         ?? throw new InvalidDataException("empty project document")).ToProject();

    private sealed record Document
    {
        public required string Id { get; init; }
        public required string Name { get; init; }
        public required string AssetLevel { get; init; }
        public required string Sheet { get; init; }
        public byte LevelId { get; init; }
        public byte TilesetId { get; init; }
        public ScrollAxis Scroll { get; init; }
        public bool Underwater { get; init; }
        public int Version { get; init; }
        public required string Map { get; init; }
        public List<OverlayDto> Overlays { get; init; } = [];
        public List<EntityDto> Entities { get; init; } = [];
        public List<LinkDto> Links { get; init; } = [];
        public List<RegionDto> Regions { get; init; } = [];
        public Dictionary<string, TileFlags> TileFlags { get; init; } = [];

        public static Document Of(EditorProject p) => new()
        {
            Id = p.Id,
            Name = p.Name,
            AssetLevel = p.AssetLevel,
            Sheet = p.Sheet,
            LevelId = p.LevelId,
            TilesetId = p.TilesetId,
            Scroll = p.Scroll,
            Underwater = p.Underwater,
            Version = p.Version,
            Map = Convert.ToBase64String(p.Map),
            Overlays = [.. p.Overlays.Select(o => new OverlayDto(o.X, o.Y, o.Overlay))],
            Entities = [.. p.Entities.Select(e =>
                new EntityDto(e.Kind, e.X, e.Y, e.Flags, e.P0, e.P1))],
            Links = [.. p.Links.Select(l => new LinkDto(l.Kind, l.Source, l.Target, l.Param))],
            Regions = [.. p.Regions.Select(r =>
                new RegionDto(r.Kind, r.X, r.Y, r.Width, r.Height))],
            TileFlags = new Dictionary<string, TileFlags>(p.TileFlags),
        };

        public EditorProject ToProject()
        {
            var map = Convert.FromBase64String(Map);
            if (map.Length != EngineLimits.MapWidth * EngineLimits.MapHeight)
                throw new InvalidDataException(
                    $"{Id}: the map is {map.Length} bytes and the engine reads "
                    + $"{EngineLimits.MapWidth}x{EngineLimits.MapHeight}");
            return new EditorProject
            {
                Id = Id,
                Name = Name,
                AssetLevel = AssetLevel,
                Sheet = Sheet,
                LevelId = LevelId,
                TilesetId = TilesetId,
                Scroll = Scroll,
                Underwater = Underwater,
                Version = Version,
                Map = map,
                Overlays = [.. Overlays.Select(o => new OverlayPlacement(o.X, o.Y, o.Tile))],
                Entities = [.. Entities.Select(e =>
                    new Entity(e.Kind, e.X, e.Y, e.Flags, e.P0, e.P1))],
                Links = [.. Links.Select(l => new Link(l.Kind, l.Source, l.Target, l.Param))],
                Regions = [.. Regions.Select(r =>
                    new Region(r.Kind, r.X, r.Y, r.Width, r.Height))],
                TileFlags = new Dictionary<string, TileFlags>(TileFlags),
            };
        }
    }

    private sealed record OverlayDto(int X, int Y, byte Tile);

    private sealed record EntityDto(
        EntityKind Kind, ushort X, ushort Y, EntityFlags Flags, byte P0, byte P1);

    private sealed record LinkDto(byte Kind, byte Source, byte Target, byte Param);

    private sealed record RegionDto(
        RegionKind Kind, ushort X, ushort Y, byte Width, byte Height);
}
