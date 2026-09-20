using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Assets;

/// <summary>
/// The artist's package into the editor's model — which for a tile sheet
/// means the PNG, its frame boxes, the names in the manifest's prose and the
/// draw table, quantised against <c>src/palette.asm</c> and packed the way
/// the engine's blitters read.
/// </summary>
/// <remarks>
/// <b>This is what stops the editor's tileset being the build's own output
/// read back.</b> Until the import existed, level 1's 41 tiles were taken
/// out of the front of <c>citytiles.bin</c> — so the bake test compared a
/// blob whose first 2,624 bytes had been copied from the file it was being
/// compared against, and only the ten baked tiles were really under test.
/// Imported from the sheet, all 3,264 are.
/// </remarks>
public static class AssetPackImporter
{
    /// <summary>
    /// One level's tiles, in the artist's frame order — which is what a map
    /// byte indexes and what the flags file is ordered by.
    /// </summary>
    /// <param name="levelDir">e.g. <c>assets/sprites/level1_city</c>.</param>
    /// <param name="paletteAsmPath"><c>src/palette.asm</c>, the engine's own sixteen pens.</param>
    /// <param name="flags">
    /// What each named tile DOES. <b>Nothing in the art package carries
    /// this</b> — see <see cref="LevelFlagSeeds"/> — so it is passed in, and
    /// a name with no entry is scenery.
    /// </param>
    /// <param name="sheetName">Which tile sheet, when a level has more than one.</param>
    public static Tileset ImportTileset(
        string levelDir,
        string paletteAsmPath,
        IReadOnlyDictionary<string, TileFlags> flags,
        string? sheetName = null)
    {
        var source = AssetPack.TileSheet(levelDir, sheetName);
        if (source.TileWidth != Tile.PixelWidth || source.TileHeight != Tile.PixelHeight)
            throw new NotSupportedException(
                $"{source.Name}: tiles are {source.TileWidth}x{source.TileHeight} and this "
                + $"engine's are {Tile.PixelWidth}x{Tile.PixelHeight} (CLAUDE.md 8.3)");

        var frames = AssetPack.Frames(source.SheetJsonPath);
        if (frames.Count != source.TileNames.Count)
            throw new InvalidDataException(
                $"{source.Name}: {frames.Count} frames in the sheet against "
                + $"{source.TileNames.Count} names in the manifest — the frame order the map's "
                + "own bytes are numbered by would be off by the difference");

        var pens = CpcPalette.ReadGamePens(paletteAsmPath);
        var image = Png.Load(source.ImagePath);

        var tiles = new List<Tile>(frames.Count);
        for (var i = 0; i < frames.Count; i++)
        {
            var box = frames[i];
            if (box.Width != Tile.PixelWidth || box.Height != Tile.PixelHeight)
                throw new InvalidDataException(
                    $"{source.Name}: frame {i} is {box.Width}x{box.Height}, not a tile");
            var name = source.TileNames[i];
            tiles.Add(new Tile
            {
                Name = name,
                Bytes = Tile.Encode(CpcPalette.Quantise(
                    image, box.X, box.Y, box.Width, box.Height, pens)),
                Flags = flags.GetValueOrDefault(name),
                IsOverlay = source.Overlays.Contains(name),
            });
        }
        return new Tileset(tiles);
    }
}
