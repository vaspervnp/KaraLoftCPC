using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Application;

/// <summary>The three files a level ships as, and the record of the bake.</summary>
public readonly record struct ExportResult(
    byte[] Level, byte[] TileFlags, byte[] Tiles,
    Tileset BakedTileset, IReadOnlyList<BakedPair> Pairs);

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
}
