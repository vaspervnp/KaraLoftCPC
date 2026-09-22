using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// <b>"Makes sense to play" is not a feeling, so it is three checks.</b>
/// The validator has to pass with nothing at all in it — every one of its
/// rules is a place the engine reads a byte and quietly does nothing
/// (CLAUDE.md 11 step 7) — she has to be able to WALK to everything the
/// level put down, and a project with no flag table has to be refused
/// rather than handed a field of scenery.
/// </summary>
public class LevelGeneratorTests
{
    private static (EditorProject Project, Tileset Tiles) Blank(int width)
    {
        var project = CitySource.Open();
        project.Width = width;
        return (project, CitySource.ArtistTiles(project));
    }

    [Theory]
    [InlineData(128)]
    [InlineData(64)]
    [InlineData(32)]
    public void Every_shape_generates_a_level_with_no_findings(int width)
    {
        var (project, tiles) = Blank(width);

        var (made, refused) = LevelGenerator.Fill(project, tiles);

        Assert.Null(refused);
        Assert.NotNull(made);
        var findings = LevelValidator.Check(project, tiles);
        Assert.Empty(findings);
    }

    [Theory]
    [InlineData(128)]
    [InlineData(64)]
    [InlineData(32)]
    public void She_can_walk_to_everything_it_placed(int width)
    {
        var (project, tiles) = Blank(width);
        LevelGenerator.Fill(project, tiles);

        var reach = Reachable(project, tiles);
        // The START is the walk's own beginning, and it is the one record
        // that is NOT on the row it stands on: it is placed a row high so
        // she falls the last 16 pixels onto the floor, which is what stops
        // a 64-line box starting inside the tiles (CLAUDE.md 8.6). That it
        // lands on something is Reachable's first step.
        Assert.Contains(reach, c => c.X == project.Entities
            .First(e => e.Kind == EntityKind.PlayerStart).X / Entity.TileWidth);
        foreach (var e in project.Entities.Where(
                     e => e.Kind is EntityKind.Pickup or EntityKind.Door))
        {
            // A RECORD'S ROW IS THE FLOOR IT STANDS ON AND NOT THE CELL IT
            // IS IN: y is the BASE of the hitbox, so the thing hangs in the
            // row above the line (CLAUDE.md 8.6). She stands there too.
            var cell = (X: e.X / Entity.TileWidth,
                        Row: e.Y / Entity.TileHeight - 1);
            Assert.True(reach.Contains(cell),
                $"{e.Kind} at tile {cell.X}, row {cell.Row} is somewhere she "
                + "cannot walk to");
        }
    }

    /// <summary>
    /// <b>The drone hovers over a floor she can walk to</b>, which is what
    /// makes it a fight rather than scenery: <c>EN_SIGHT</c> is horizontal
    /// and <c>EN_H_SIGHT</c> is 40 lines, so an enemy over a floor she
    /// cannot reach is one that can never see her (CLAUDE.md 8.7). The
    /// floor is found by walking rather than by restating the hover.
    /// </summary>
    [Theory]
    [InlineData(128)]
    [InlineData(64)]
    [InlineData(32)]
    public void Every_enemy_hovers_over_a_floor_she_can_reach(int width)
    {
        var (project, tiles) = Blank(width);
        LevelGenerator.Fill(project, tiles);
        var reach = Reachable(project, tiles);

        var enemies = project.Entities.Where(e => e.Kind == EntityKind.Enemy).ToList();
        Assert.NotEmpty(enemies);
        foreach (var drone in enemies)
        {
            var col = drone.X / Entity.TileWidth;
            var row = drone.Y / Entity.TileHeight;
            var floor = reach.Where(c => c.X == col && c.Row >= row)
                             .OrderBy(c => c.Row).ToList();
            Assert.True(floor.Count > 0,
                $"the drone at tile {col}, row {row} has no floor under it she "
                + "can walk to");
            Assert.True(floor[0].Row - row <= 1,
                $"the nearest floor under the drone at tile {col} is "
                + $"{floor[0].Row - row} rows down, which is out of its sight");
        }
    }

    /// <summary>
    /// <b>And on a shaft it is past world line 255, which is the whole of
    /// why <c>ES_Y</c> is a word.</b> It goes on the floors in the MIDDLE of
    /// the descent — an enemy on the second floor is a level that opens
    /// with a fight — and the middle of a 64-row map is below what a byte
    /// reaches (CLAUDE.md 8.7).
    /// </summary>
    [Fact]
    public void On_a_tall_map_the_drone_is_below_what_a_byte_reaches()
    {
        var (project, tiles) = Blank(32);

        LevelGenerator.Fill(project, tiles);

        var drone = Assert.Single(project.Entities,
                                  e => e.Kind == EntityKind.Enemy);
        Assert.True(drone.Y > byte.MaxValue,
            $"the drone's world Y is {drone.Y}, which a byte still holds");
    }

    [Fact]
    public void A_project_with_no_flags_is_refused_and_says_which_role()
    {
        var (project, tiles) = Blank(32);
        project.TileFlags.Clear();

        var (made, refused) = LevelGenerator.Fill(project, tiles);

        Assert.Null(made);
        Assert.Contains("Solid", refused);
    }

    [Fact]
    public void And_with_a_floor_but_no_ladder_it_names_that_one_instead()
    {
        var (project, tiles) = Blank(32);
        var floor = project.TileFlags.First(f => f.Value.HasFlag(TileFlags.Solid)
                                                 && !f.Value.HasFlag(TileFlags.Ladder));
        project.TileFlags.Clear();
        project.TileFlags[floor.Key] = floor.Value;

        var (made, refused) = LevelGenerator.Fill(project, tiles);

        Assert.Null(made);
        Assert.Contains("Ladder", refused);
    }

    /// <summary>
    /// The cells she can stand on and get to: walk along a run of floor,
    /// and change floor only where a ladder joins two. A hole in the floor
    /// stops the walk, which is the conservative reading — she can run-jump
    /// three tiles (CLAUDE.md 8.8) and this does not credit her with it.
    /// </summary>
    private static HashSet<(int X, int Row)> Reachable(EditorProject project,
                                                       Tileset tiles)
    {
        bool Stands(int x, int row)
        {
            if (row + 1 >= project.Height || x < 0 || x >= project.Width) return false;
            var under = tiles[project.Map[(row + 1) * project.Width + x]].Name;
            project.TileFlags.TryGetValue(under, out var f);
            return f.HasFlag(TileFlags.Solid) || f.HasFlag(TileFlags.Platform);
        }
        bool Shaft(int x, int row)
        {
            if (row < 0 || row >= project.Height) return false;
            var here = tiles[project.Map[row * project.Width + x]].Name;
            project.TileFlags.TryGetValue(here, out var f);
            return f.HasFlag(TileFlags.Ladder);
        }

        var start = project.Entities.First(e => e.Kind == EntityKind.PlayerStart);
        // She is placed one row ABOVE the floor and falls onto it.
        var from = (X: start.X / Entity.TileWidth, Row: start.Y / Entity.TileHeight);
        if (!Stands(from.X, from.Row)) from = (from.X, from.Row + 1);

        var seen = new HashSet<(int, int)>();
        var queue = new Queue<(int X, int Row)>();
        queue.Enqueue(from);
        while (queue.Count > 0)
        {
            var (x, row) = queue.Dequeue();
            if (!seen.Add((x, row))) continue;
            foreach (var nx in new[] { x - 1, x + 1 })
                if (Stands(nx, row)) queue.Enqueue((nx, row));
            // a ladder under her feet, or one she is standing on
            for (var r = row + 1; Shaft(x, r); r++)
                if (Stands(x, r)) { queue.Enqueue((x, r)); break; }
            for (var r = row - 1; r >= 0 && Shaft(x, r); r--)
                if (Stands(x, r)) { queue.Enqueue((x, r)); break; }
            if (Shaft(x, row))
            {
                for (var r = row + 1; r < project.Height && Shaft(x, r); r++)
                    if (Stands(x, r)) { queue.Enqueue((x, r)); break; }
                for (var r = row - 1; r >= 0 && Shaft(x, r); r--)
                    if (Stands(x, r)) { queue.Enqueue((x, r)); break; }
            }
        }
        return seen;
    }
}
