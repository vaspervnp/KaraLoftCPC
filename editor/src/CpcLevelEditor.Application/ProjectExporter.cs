using System.Text;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Application;

/// <summary>The three files a level ships as, and the record of the bake.</summary>
public readonly record struct ExportResult(
    byte[] Level, byte[] TileFlags, byte[] Tiles,
    Tileset BakedTileset, IReadOnlyList<BakedPair> Pairs);

/// <summary>One file of an export, named the way the build names it.</summary>
public readonly record struct ExportFile(string Name, byte[] Bytes);

/// <summary>
/// A project into the bytes the engine reads: <c>level_&lt;n&gt;.lvl</c>,
/// <c>tileflags_&lt;level&gt;.bin</c> and the tileset blob.
/// </summary>
/// <remarks>
/// <b>The overlay layer dies here and the format never learns about it.</b>
/// The designer's map holds the artist's tiles with a layer of
/// (overlay, background) pairs over it; the bake composites each distinct
/// pair into a new tile, appends it to the tileset and points the cell at
/// it, so what leaves is a map whose every cell is a finished tile
/// (CLAUDE.md 7.3, 8.3). That is the same trade <c>ENT_BAKE</c> makes for
/// the pickups: 64 bytes of bank per pair against 1,338-2,007 T a cell for
/// a masked blitter the frame cannot pay for.
/// </remarks>
public static class ProjectExporter
{
    public static ExportResult Export(EditorProject project, Tileset artistTiles)
    {
        var baked = new OverlayBaker().Bake(project.ToLevel(), artistTiles);

        var level = new Level
        {
            LevelId = project.LevelId,
            TilesetId = project.TilesetId,
            Width = project.Width,
            Height = project.Height,
            Scroll = project.Scroll,
            Underwater = project.Underwater,
            Map = baked.Map,
            Entities = [.. project.Entities],
            Links = [.. project.Links],
            Regions = [.. project.Regions],
        };

        return new ExportResult(
            new BinaryLevelExporter().Write(level),
            new TileFlagsExporter().Write(baked.Tileset),
            baked.Tileset.ToBlob(),
            baked.Tileset,
            baked.Pairs);
    }

    /// <summary>
    /// The export as named files.
    /// </summary>
    /// <remarks>
    /// <b>The fourth is not a binary and is not optional.</b> The three the
    /// engine reads say nothing about which cells were an overlay on a wall,
    /// so a level exported without its bake record is one this editor can
    /// never open again — its own output included (<see cref="BakeRecord"/>).
    /// The names are the build's, so the four drop straight into
    /// <c>build/</c>.
    /// </remarks>
    public static IReadOnlyList<ExportFile> Files(
        EditorProject project, ExportResult result) =>
    [
        new($"level_{project.LevelId}.lvl", result.Level),
        new($"tileflags_{project.AssetLevel}.bin", result.TileFlags),
        new($"{project.Sheet.Replace("_tiles", "tiles", StringComparison.Ordinal)}.bin",
            result.Tiles),
        new(BakeRecord.FileName(project.Sheet),
            Encoding.UTF8.GetBytes(BakeRecord.Write(result.Pairs))),
    ];

    /// <summary>
    /// ... and on disk, because a designer who has to fish four files out of
    /// a browser's downloads folder and move them by hand has a step that can
    /// be got wrong, and the tool is local anyway.
    /// </summary>
    public static IReadOnlyList<ExportFile> WriteTo(
        string directory, EditorProject project, ExportResult result)
    {
        var files = Files(project, result);
        Directory.CreateDirectory(directory);
        foreach (var file in files)
            File.WriteAllBytes(Path.Combine(directory, file.Name), file.Bytes);
        return files;
    }
}
