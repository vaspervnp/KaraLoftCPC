using System.Text.Json;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The files the build already produces, which are what this editor has to
/// agree with. They are read from the repository rather than copied into the
/// test project: a copied golden file stops being golden the first time the
/// generator changes and nobody re-copies it.
/// </summary>
internal static class Golden
{
    /// <summary>
    /// Walks up from the test binary until it finds the repository, which is
    /// the directory with CLAUDE.md in it.
    /// </summary>
    public static string RepoRoot { get; } = FindRepoRoot();

    public static string Build(string name) => Path.Combine(RepoRoot, "build", name);

    public static string Asset(params string[] parts) =>
        Path.Combine([RepoRoot, "assets", .. parts]);

    public static byte[] Bytes(string path) => File.ReadAllBytes(path);

    /// <summary>The level's own file: 21 bytes of header, 2,048 of map, 80 of entities.</summary>
    public static byte[] Level1 => Bytes(Build("level_1.lvl"));

    /// <summary>41 of the artist's tiles and 10 baked, 64 bytes each.</summary>
    public static byte[] CityTiles =>
        Bytes(Path.Combine(RepoRoot, "build", "levels", "level1_city", "citytiles.bin"));

    /// <summary>One byte a tile, the table TILE_ATTR holds.</summary>
    public static byte[] CityTileFlags => Bytes(Build("tileflags_level1_city.bin"));

    /// <summary>The full 24-slot table; only the live prefix goes into the .lvl.</summary>
    public static byte[] CityEntities => Bytes(Build("city_entities.bin"));

    /// <summary>What the build baked, and what it dropped.</summary>
    public static IReadOnlyList<BakedRecord> CityBaked =>
        JsonSerializer.Deserialize<List<BakedRecord>>(
            File.ReadAllText(Build("city_baked.json")),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
        ?? throw new InvalidDataException("build/city_baked.json is empty");

    /// <summary>
    /// The tile names, in frame order, out of the manifest's description
    /// field — which is where <c>make_city_map.py</c>'s own
    /// <c>tile_names()</c> reads them. <c>tile_names</c> as a key exists only
    /// in levels 3 and 5, so this is the route that works for level 1.
    /// </summary>
    public static string[] CityTileNames()
    {
        using var doc = JsonDocument.Parse(
            File.ReadAllText(Asset("sprites", "level1_city", "manifest.json")));
        foreach (var sheet in doc.RootElement.GetProperty("sheets").EnumerateArray())
        {
            if (sheet.GetProperty("name").GetString() != "city_tiles")
                continue;
            var description = sheet.GetProperty("description").GetString()!;
            var order = description.Split("frame order:", 2)[1].Split('.', 2)[0];
            return [.. order.Split(',').Select(n => n.Trim())];
        }
        throw new InvalidDataException("no city_tiles sheet in level1_city/manifest.json");
    }

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "CLAUDE.md")))
            dir = dir.Parent;
        return dir?.FullName
            ?? throw new DirectoryNotFoundException(
                "no CLAUDE.md above " + AppContext.BaseDirectory);
    }
}

/// <summary>One record of <c>build/city_baked.json</c>.</summary>
internal sealed record BakedRecord(int Index, int Over, int Under, string Name, bool Baked);
