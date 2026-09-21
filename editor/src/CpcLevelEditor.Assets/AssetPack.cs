using System.Text.Json;

namespace CpcLevelEditor.Assets;

/// <summary>One frame box of an Aseprite sheet export.</summary>
public readonly record struct SheetFrame(int X, int Y, int Width, int Height);

/// <summary>
/// Everything about one tile sheet that the three files in the art package
/// between them say: what the tiles are called, which of them are overlays,
/// how big they are, and where the pixels live.
/// </summary>
public sealed record TileSheetSource(
    string Name,
    string ImagePath,
    string SheetJsonPath,
    int TileWidth,
    int TileHeight,
    IReadOnlyList<string> TileNames,
    IReadOnlySet<string> Overlays);

/// <summary>
/// Reading the artist's package — and three things in it are not what
/// docs/editor.md 4 assumes, all found by reading the shipped files.
/// </summary>
/// <remarks>
/// <list type="bullet">
/// <item><b>The manifest's <c>file</c> fields point at nothing.</b> Every
/// sheet names an <c>out/frames_*.txt</c> that is not in the package, so the
/// PNG and its JSON are found by <c>tile_table.json</c>'s own <c>file</c>
/// field and, failing that, by scanning the directory.</item>
/// <item><b>Only <c>tile_table.json</c> names every tile.</b> Counted over
/// the package's nine tile sheets: two carry a <c>tile_names</c> list in the
/// manifest (levels 3 and 5), one states the frame order in prose in its
/// <c>description</c> (level 1, which is where
/// <c>tools/make_city_map.py</c> reads it and therefore where the shipped
/// level's own byte order comes from) — and <b>five say nothing at all</b>.
/// The derived table has all 275 of them, indexed 0..n-1 and unique in
/// every sheet, so that is the source; <see cref="ManifestTileNames"/> is
/// kept for the level-1 cross-check, where two independent statements of
/// the same order have to agree.</item>
/// <item><b>Which tiles are overlays is a TABLE, never the pixels.</b>
/// <c>tile_table.json</c> is the manifest's <c>overlay</c> list resolved
/// against the real art, and it is the only thing that says so: over the six
/// levels, 69 tiles carry pen 0 and only 34 are overlays, the emptiest
/// opaque one being <c>sky_stars</c> at 126 pixels of 128 and the fullest
/// overlay the cave's <c>beam_top</c> at 14 (CLAUDE.md 7.3). There is no
/// pixel count that separates them.</item>
/// </list>
/// </remarks>
public static class AssetPack
{
    /// <summary>
    /// The one sheet of <paramref name="levelDir"/> whose <c>kind</c> is
    /// <c>tiles</c> and whose name is <paramref name="sheetName"/>, or the
    /// first tile sheet when no name is given.
    /// </summary>
    public static TileSheetSource TileSheet(string levelDir, string? sheetName = null)
    {
        using var manifest = JsonDocument.Parse(
            File.ReadAllText(Path.Combine(levelDir, "manifest.json")));
        using var table = JsonDocument.Parse(
            File.ReadAllText(Path.Combine(levelDir, "tile_table.json")));

        var sheet = manifest.RootElement.GetProperty("sheets").EnumerateArray()
            .FirstOrDefault(s =>
                s.TryGetProperty("kind", out var kind) && kind.GetString() == "tiles"
                && (sheetName is null || s.GetProperty("name").GetString() == sheetName));
        if (sheet.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException(
                $"{levelDir}: no tiles sheet{(sheetName is null ? "" : " called " + sheetName)}");

        var name = sheet.GetProperty("name").GetString()!;
        var size = sheet.GetProperty("size").EnumerateArray().Select(v => v.GetInt32()).ToArray();

        var entry = table.RootElement.GetProperty("sheets").EnumerateArray()
            .FirstOrDefault(s => s.GetProperty("sheet").GetString() == name);
        if (entry.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException($"{levelDir}: {name} is not in tile_table.json");

        var image = Path.Combine(levelDir, entry.GetProperty("file").GetString()!);
        if (!File.Exists(image))
            image = Scan(levelDir, name, ".png");
        var json = Path.ChangeExtension(image, ".json");
        if (!File.Exists(json))
            json = Scan(levelDir, name, ".json");

        var overlays = new HashSet<string>(StringComparer.Ordinal);
        foreach (var tile in entry.GetProperty("tiles").EnumerateArray())
            if (tile.GetProperty("draw").GetString() == "overlay")
                overlays.Add(tile.GetProperty("name").GetString()!);

        var names = new List<string>();
        var index = 0;
        foreach (var tile in entry.GetProperty("tiles").EnumerateArray())
        {
            if (tile.GetProperty("index").GetInt32() != index++)
                throw new InvalidDataException(
                    $"{levelDir}: {name}'s tile_table is not in index order, and the "
                    + "order IS what a map byte means");
            names.Add(tile.GetProperty("name").GetString()!);
        }

        return new TileSheetSource(
            name, image, json, size[0], size[1], names, overlays);
    }

    /// <summary>
    /// What the MANIFEST says the frame order is, for the sheets that say —
    /// a <c>tile_names</c> list, or the prose after "frame order:" and
    /// before the first full stop. Five of the package's nine tile sheets
    /// state neither, which is why this is a cross-check and not the source.
    /// </summary>
    public static IReadOnlyList<string>? ManifestTileNames(string levelDir, string sheetName)
    {
        using var manifest = JsonDocument.Parse(
            File.ReadAllText(Path.Combine(levelDir, "manifest.json")));
        var sheet = manifest.RootElement.GetProperty("sheets").EnumerateArray()
            .FirstOrDefault(s => s.GetProperty("name").GetString() == sheetName);
        if (sheet.ValueKind != JsonValueKind.Object)
            return null;

        if (sheet.TryGetProperty("tile_names", out var listed))
            return [.. listed.EnumerateArray().Select(n => n.GetString()!)];

        if (!sheet.TryGetProperty("description", out var described))
            return null;
        var prose = described.GetString()!;
        var at = prose.IndexOf("frame order:", StringComparison.Ordinal);
        if (at < 0)
            return null;
        var order = prose[(at + "frame order:".Length)..].Split('.', 2)[0];
        return [.. order.Split(',').Select(n => n.Trim())];
    }

    /// <summary>
    /// The tile sheets a level has. Most have one; level 3 carries the
    /// quake's flood and level 6 the laser beams as a second sheet.
    /// </summary>
    public static IReadOnlyList<string> TileSheetNames(string levelDir)
    {
        using var manifest = JsonDocument.Parse(
            File.ReadAllText(Path.Combine(levelDir, "manifest.json")));
        return [.. manifest.RootElement.GetProperty("sheets").EnumerateArray()
            .Where(s => s.TryGetProperty("kind", out var kind) && kind.GetString() == "tiles")
            .Select(s => s.GetProperty("name").GetString()!)];
    }

    /// <summary>The frame boxes, which Aseprite writes as a list or as an object.</summary>
    public static IReadOnlyList<SheetFrame> Frames(string sheetJsonPath)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(sheetJsonPath));
        var frames = doc.RootElement.GetProperty("frames");
        var boxes = frames.ValueKind == JsonValueKind.Array
            ? frames.EnumerateArray()
            : frames.EnumerateObject().Select(p => p.Value);
        return [.. boxes.Select(f =>
        {
            var box = f.GetProperty("frame");
            return new SheetFrame(
                box.GetProperty("x").GetInt32(), box.GetProperty("y").GetInt32(),
                box.GetProperty("w").GetInt32(), box.GetProperty("h").GetInt32());
        })];
    }

    private static string Scan(string levelDir, string sheet, string extension)
    {
        var found = Directory.GetFiles(levelDir, $"{sheet}*_sheet{extension}");
        return found.Length == 1
            ? found[0]
            : throw new FileNotFoundException(
                $"{levelDir}: {found.Length} candidates for {sheet}'s {extension} sheet");
    }
}
