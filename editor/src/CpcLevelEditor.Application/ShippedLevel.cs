using CpcLevelEditor.Assets;

namespace CpcLevelEditor.Application;

/// <summary>
/// The level the game already plays, opened as something a designer can
/// paint.
/// </summary>
/// <remarks>
/// It is two files and not one: the <c>.lvl</c> for the map, the entities
/// and the header, and the bake's record beside it for the overlay layer the
/// format has no room to carry (<see cref="LevelUnbaker"/>,
/// <see cref="BakeRecord"/>). Whether the pair was written by
/// <c>tools/make_city_map.py</c> or by this editor's own export makes no
/// difference — that is the point of writing the record in the generator's
/// shape.
/// </remarks>
public static class ShippedLevel
{
    /// <summary>What to open, and what to call the project it becomes.</summary>
    public sealed record Request
    {
        public required string Id { get; init; }
        public required string Name { get; init; }
        public string AssetLevel { get; init; } = "level1_city";
        public string Sheet { get; init; } = "city_tiles";

        /// <summary>The directory holding the level and its bake record.</summary>
        public required string From { get; init; }

        /// <summary>Which <c>level_&lt;n&gt;.lvl</c> to read.</summary>
        public byte LevelId { get; init; } = 1;
    }

    public static EditorProject Open(Request request, AssetCatalogue assets)
    {
        var levelFile = Path.Combine(request.From, $"level_{request.LevelId}.lvl");
        var recordFile = Path.Combine(request.From, BakeRecord.FileName(request.Sheet));
        var baked = new Exporters.BinaryLevelReader().Read(File.ReadAllBytes(levelFile));
        var pairs = BakeRecord.Read(File.ReadAllText(recordFile));

        var flags = LevelFlagSeeds.For(request.AssetLevel);
        var artist = assets.Tileset(request.AssetLevel, request.Sheet, flags);
        var source = LevelUnbaker.Unbake(baked, pairs, artist.Count);

        return new EditorProject
        {
            Id = request.Id,
            Name = request.Name,
            AssetLevel = request.AssetLevel,
            Sheet = request.Sheet,
            LevelId = baked.LevelId,
            TilesetId = baked.TilesetId,
            Scroll = baked.Scroll,
            Underwater = baked.Underwater,
            Map = source.Map,
            Overlays = [.. source.Overlays],
            Entities = [.. baked.Entities],
            Links = [.. baked.Links],
            Regions = [.. baked.Regions],
            TileFlags = new Dictionary<string, Domain.TileFlags>(flags),
        };
    }
}
