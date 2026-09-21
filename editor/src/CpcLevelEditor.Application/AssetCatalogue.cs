using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

/// <summary>
/// The art package, imported once and handed out with a project's own tile
/// flags on it.
/// </summary>
/// <remarks>
/// The pixels are the artist's and never change while the editor runs; what
/// a tile DOES is the designer's and changes as they work, so the cache
/// holds the sheet and the flags go on at the door. Keying the cache on the
/// flags as well would hold a tileset per keystroke.
/// </remarks>
public sealed class AssetCatalogue(string spritesRoot, string paletteAsmPath)
{
    private readonly Dictionary<(string Level, string Sheet), Tileset> _sheets = [];
    private readonly Lock _gate = new();

    public string SpritesRoot { get; } = spritesRoot;

    /// <summary>The engine's sixteen pens, as RGB, for anything that has to draw.</summary>
    public (byte R, byte G, byte B)[] Palette { get; } =
        [.. CpcPalette.ReadGamePens(paletteAsmPath)
            .Select(hw => CpcPalette.HardwareColours[hw])];

    /// <summary>The levels the package holds, as directory names.</summary>
    public IReadOnlyList<string> Levels() =>
        [.. Directory.GetDirectories(SpritesRoot, "level*_*")
            .Select(Path.GetFileName).OfType<string>().Order()];

    /// <summary>The tile sheets of one level.</summary>
    public IReadOnlyList<string> Sheets(string assetLevel) =>
        AssetPack.TileSheetNames(Path.Combine(SpritesRoot, assetLevel));

    public Tileset TilesetFor(EditorProject project) =>
        Tileset(project.AssetLevel, project.Sheet, project.TileFlags);

    public Tileset Tileset(
        string assetLevel, string sheet, IReadOnlyDictionary<string, TileFlags> flags)
    {
        Tileset cached;
        lock (_gate)
        {
            if (!_sheets.TryGetValue((assetLevel, sheet), out var found))
            {
                found = AssetPackImporter.ImportTileset(
                    Path.Combine(SpritesRoot, assetLevel), paletteAsmPath,
                    new Dictionary<string, TileFlags>(), sheet);
                _sheets[(assetLevel, sheet)] = found;
            }
            cached = found;
        }

        return new Tileset(cached.Tiles.Select(t => new Tile
        {
            Name = t.Name,
            Bytes = t.Bytes,
            IsOverlay = t.IsOverlay,
            Flags = flags.GetValueOrDefault(t.Name),
        }));
    }
}
