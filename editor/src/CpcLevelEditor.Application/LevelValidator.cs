using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

public enum Severity
{
    /// <summary>The engine would refuse it, or play it wrong.</summary>
    Error,

    /// <summary>It loads and something about it is probably not meant.</summary>
    Warning,
}

public readonly record struct Finding(Severity Severity, string Rule, string Message);

/// <summary>
/// What the engine will actually accept, checked before a designer finds out
/// on the hardware.
/// </summary>
/// <remarks>
/// Every rule here is somewhere in CLAUDE.md with a measurement under it;
/// none of them is a matter of taste. The validator is deliberately on the
/// SERVER and written once (docs/editor.md 6.3): a second copy in the
/// browser would be two versions of the same rules, and the rules are the
/// part that has to be right.
/// </remarks>
public static class LevelValidator
{
    public static IReadOnlyList<Finding> Check(EditorProject project, Tileset artistTiles)
    {
        var findings = new List<Finding>();

        foreach (var problem in project.ToLevel().Problems())
            findings.Add(new Finding(Severity.Error, "engine-limits", problem));

        for (var cell = 0; cell < project.Map.Length; cell++)
            if (project.Map[cell] >= artistTiles.Count)
            {
                findings.Add(new Finding(Severity.Error, "tile-index",
                    $"cell ({cell % project.Width},{cell / project.Width}) points at tile "
                    + $"{project.Map[cell]} and the sheet has {artistTiles.Count}"));
                break;
            }

        foreach (var placement in project.Overlays)
        {
            if ((uint)placement.X >= project.Width || (uint)placement.Y >= project.Height)
            {
                findings.Add(new Finding(Severity.Error, "overlay-bounds",
                    $"an overlay sits at ({placement.X},{placement.Y}), off a "
                    + $"{project.Width}x{project.Height} map"));
                continue;
            }
            if (placement.Overlay >= artistTiles.Count)
            {
                findings.Add(new Finding(Severity.Error, "overlay-tile",
                    $"overlay tile {placement.Overlay} is past the end of the sheet"));
                continue;
            }
            // NOTHING ABOUT A TILE'S PIXELS SAYS IT IS AN OVERLAY, only the
            // artist's table does (CLAUDE.md 7.3) - so an opaque tile placed
            // as an overlay composites to itself and silently wastes 64 bytes
            // of bank on a tile that is already there.
            if (!artistTiles[placement.Overlay].IsOverlay)
                findings.Add(new Finding(Severity.Warning, "overlay-opaque",
                    $"\"{artistTiles[placement.Overlay].Name}\" is opaque in the artist's "
                    + "table, so composited it covers whatever is under it completely"));
        }

        // The bake APPENDS, and the top sixteen tiles of bank C4 are not the
        // allocator's to give: ENT_BAKE stamps the pickups into 240-255 at
        // run time (CLAUDE.md 8.6).
        var pairs = project.Overlays
            .Select(p => (p.Overlay, Under: project.Map[p.Y * project.Width + p.X]))
            .Distinct().Count();
        if (artistTiles.Count + pairs > EngineLimits.ScratchTileFirst)
            findings.Add(new Finding(Severity.Error, "tile-budget",
                $"{artistTiles.Count} tiles and {pairs} distinct overlay pairs would reach "
                + $"tile {artistTiles.Count + pairs - 1}, and the pickup bake owns "
                + $"{EngineLimits.ScratchTileFirst}-255"));

        var worldWidth = project.Width * Entity.TileWidth;
        var worldHeight = project.Height * Entity.TileHeight;
        for (var i = 0; i < project.Entities.Count; i++)
        {
            var entity = project.Entities[i];
            if (entity.X >= worldWidth || entity.Y > worldHeight)
                findings.Add(new Finding(Severity.Error, "entity-bounds",
                    $"entity {i} is at ({entity.X},{entity.Y}) in a world of "
                    + $"{worldWidth}x{worldHeight} pixels"));
        }

        var starts = project.Entities.Count(e => e.Kind == EntityKind.PlayerStart);
        if (starts == 0)
            findings.Add(new Finding(Severity.Warning, "player-start",
                "no EK_PLAYER_START: kind 0 is the player's, so a level without one "
                + "starts her wherever SCROLL_INIT last left her"));
        else if (starts > 1)
            findings.Add(new Finding(Severity.Warning, "player-start",
                $"{starts} EK_PLAYER_START records: the engine sweeps the table in order "
                + "and nothing says which of them is meant"));

        // A REGION IS IN TILES, which is what its byte-wide width and height
        // are for (Region). Nothing in the engine reads one yet, so this is
        // the only thing standing between a designer and a record that says
        // something impossible.
        for (var i = 0; i < project.Regions.Count; i++)
        {
            var region = project.Regions[i];
            if (region.Width == 0 || region.Height == 0)
                findings.Add(new Finding(Severity.Error, "region-bounds",
                    $"region {i} is {region.Width}x{region.Height} tiles and covers nothing"));
            else if (region.X + region.Width > project.Width
                     || region.Y + region.Height > project.Height)
                findings.Add(new Finding(Severity.Error, "region-bounds",
                    $"region {i} is {region.Width}x{region.Height} at "
                    + $"({region.X},{region.Y}) and runs off a "
                    + $"{project.Width}x{project.Height} map"));
        }

        return findings;
    }
}
