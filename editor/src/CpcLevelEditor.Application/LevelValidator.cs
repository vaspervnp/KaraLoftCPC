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
            findings.AddRange(EngineWillUse(i, entity));
        }

        // A PICKUP IS DRAWN BY BEING BAKED, AND THERE ARE SIXTEEN TILES TO
        // BAKE INTO (EngineLimits.BakedPickups). ENT_MAX is 24, so a level
        // can hold more pickups than the engine can draw and the extras
        // are invisible AND takeable.
        var pickups = project.Entities.Count(
            e => e.Kind == EntityKind.Pickup && e.IsActive);
        if (pickups > EngineLimits.BakedPickups)
            findings.Add(new Finding(Severity.Error, "pickup-budget",
                $"{pickups} pickups against ENT_BAKE_MAX = {EngineLimits.BakedPickups} "
                + "scratch tiles: ENT_BAKE stops when they run out and the rest are "
                + "drawn nowhere - still there to walk into, out of a cell showing "
                + "whatever was under them"));

        findings.AddRange(EnemiesSharingAScreen(project));

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

    /// <summary>
    /// What the engine will make of ONE record, as against what the format
    /// will carry.
    /// </summary>
    /// <remarks>
    /// Every rule here is a place where <c>src/entity.asm</c> or
    /// <c>src/enemy.asm</c> tests a byte and quietly does nothing when it
    /// does not like it. That is the right behaviour for the engine — a
    /// level it cannot read should lose a record, not the frame — and it is
    /// exactly why a designer needs telling: nothing on the hardware says
    /// which of the records was skipped.
    /// </remarks>
    private static IEnumerable<Finding> EngineWillUse(int i, Entity entity)
    {
        // p0 IS ALWAYS "WHICH THING THIS IS" (CLAUDE.md 8.6), and both
        // readers bound it against their own table.
        if (entity.Kind == EntityKind.Pickup && !Enum.IsDefined((PickupKind)entity.P0))
            yield return new Finding(Severity.Error, "pickup-kind",
                $"entity {i} is a pickup with p0 = {entity.P0}, and ENT_BAKE_ONE "
                + $"refuses anything at or past ENT_ART_KINDS = {Enum.GetValues<PickupKind>().Length}: "
                + "it is drawn nowhere and it goes into no counter when she walks "
                + "into it");

        if (entity.Kind == EntityKind.Enemy && !Enum.IsDefined((EnemyKind)entity.P0))
            yield return new Finding(Severity.Error, "enemy-kind",
                $"entity {i} is an enemy with p0 = {entity.P0}, and ENEMY_ADD refuses "
                + $"anything at or past EN_KINDS = {Enum.GetValues<EnemyKind>().Length}: "
                + "the record costs a slot of ENT_MAX and nothing ever spawns");

        if (entity.Kind != EntityKind.Pickup)
        {
            // ENTITY_COLLISION_CHECK publishes the FIRST record whose box
            // meets hers and stops, and ENT_ON_TOUCH does nothing with
            // anything but a pickup - so a touchable door standing over a
            // pickup is a pickup she cannot take.
            if (entity.Flags.HasFlag(EntityFlags.Touch))
                yield return new Finding(Severity.Warning, "touch-not-pickup",
                    $"entity {i} ({entity.Kind}) carries EF_TOUCH, which ENT_ON_TOUCH "
                    + "does nothing with - and the touch sweep stops at the first box "
                    + "it meets, so this one hides any pickup it overlaps");
            yield break;
        }

        // ... and the rest are the pickup's own.
        if (!entity.Flags.HasFlag(EntityFlags.Touch))
            yield return new Finding(Severity.Error, "pickup-touch",
                $"entity {i} is a pickup without EF_TOUCH. ENT_ON_TOUCH is the only "
                + "handler that takes one and it runs on the EF_TOUCH sweep; the "
                + "interact pass has doors, NPCs and receptacles in it and nothing "
                + "else - so this one is drawn and cannot be picked up");

        // A PICKUP SITS ON THE TILE GRID. ENT_BAKE stamps it into the cell
        // its TOP-LEFT falls in - an unaligned one would need four scratch
        // tiles instead of one (CLAUDE.md 8.6) - while the AABB stays where
        // the record says. Off the grid, the picture and the hitbox part.
        if (entity.X % Entity.TileWidth != 0 || entity.Y % Entity.TileHeight != 0)
            yield return new Finding(Severity.Error, "pickup-grid",
                $"entity {i} is a pickup at ({entity.X},{entity.Y}), which is not a "
                + $"whole {Entity.TileWidth}x{Entity.TileHeight} cell: ENT_BAKE draws "
                + "it in the cell its top-left falls in and the box stays here, so "
                + "the picture and the thing she can walk into are in different places");
    }

    /// <summary>
    /// <b>One enemy on screen at a time is a property of the LEVEL.</b>
    /// </summary>
    /// <remarks>
    /// <para>
    /// <c>ENEMY_PICK</c> takes the first record it finds near the view and
    /// keeps it, so two that can be seen together mean one of them silently
    /// not being there. Scanning strictly and falling back was written and
    /// measured — <c>764 T to 2,656</c> on every frame with nothing
    /// drawable — and thrown away, because over the length of level 1's
    /// roof it never once changed the answer (CLAUDE.md 8.7).
    /// </para>
    /// <para>
    /// So the check belongs here, where <c>tools/make_city_map.py</c>
    /// already asserts it for the generated City. The beat is the patrol:
    /// <c>p1</c> is its half-width in TILES, so an enemy occupies
    /// <c>x ± p1</c> and no two of those may come within a screen of each
    /// other.
    /// </para>
    /// </remarks>
    private static IEnumerable<Finding> EnemiesSharingAScreen(EditorProject project)
    {
        var beats = project.Entities
            .Where(e => e.Kind == EntityKind.Enemy && e.IsActive)
            .Select(e => (Low: e.X / Entity.TileWidth - e.P1,
                          High: e.X / Entity.TileWidth + e.P1))
            .OrderBy(b => b.Low).ThenBy(b => b.High)
            .ToList();

        for (var i = 1; i < beats.Count; i++)
            if (beats[i].Low - beats[i - 1].High <= EngineLimits.ScreenTilesAcross)
                yield return new Finding(Severity.Error, "enemy-spacing",
                    $"two enemies can be on screen at once: one patrols out to tile "
                    + $"{beats[i - 1].High} and the next starts at {beats[i].Low}, "
                    + $"against a screen {EngineLimits.ScreenTilesAcross} tiles wide. "
                    + "ENEMY_PICK keeps the first it finds, so the other one is simply "
                    + "not there");
    }
}
