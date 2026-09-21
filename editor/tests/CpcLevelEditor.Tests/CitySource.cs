using System.Text.Json;
using CpcLevelEditor.Application;
using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The shipped City, taken apart into a project a designer could paint —
/// the map's composited cells back into the artist's tiles and the overlay
/// layer that was over them.
/// </summary>
internal static class CitySource
{
    public static EditorProject Open()
    {
        var baked = new BinaryLevelReader().Read(Golden.Level1);
        var pairs = Golden.CityBaked
            .Select(r => new BakedPair(r.Index, r.Over, r.Under, r.Name, r.Baked))
            .ToArray();
        var source = LevelUnbaker.Unbake(baked, pairs, Level1City.ArtistTileCount);

        return new EditorProject
        {
            Id = "city",
            Name = "Level 1 — the City",
            AssetLevel = "level1_city",
            Sheet = "city_tiles",
            LevelId = baked.LevelId,
            TilesetId = baked.TilesetId,
            Scroll = baked.Scroll,
            Underwater = baked.Underwater,
            Map = source.Map,
            Overlays = [.. source.Overlays],
            Entities = [.. baked.Entities],
            Links = [.. baked.Links],
            Regions = [.. baked.Regions],
            TileFlags = new Dictionary<string, TileFlags>(LevelFlagSeeds.City),
        };
    }

    public static Tileset ArtistTiles(EditorProject project) =>
        AssetPackImporter.ImportTileset(
            Golden.Asset("sprites", project.AssetLevel), Golden.PaletteAsm,
            project.TileFlags, project.Sheet);

    /// <summary>The catalogue, pointed at this repository's own art.</summary>
    public static AssetCatalogue Catalogue() =>
        new(Golden.Asset("sprites"), Golden.PaletteAsm);

    /// <summary>A scratch directory for a store, cleaned up by the caller.</summary>
    public static string TemporaryRoot() =>
        Directory.CreateTempSubdirectory("cpc-editor-").FullName;

    internal static JsonSerializerOptions Lenient { get; } =
        new() { PropertyNameCaseInsensitive = true };
}
