using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

/// <summary>What a generated level came out as, for the designer to read.</summary>
public readonly record struct GeneratedLevel(
    int Floors, int Ladders, int Holes, int Pickups, int Enemies,
    string FloorTile, string LadderTile, string BackgroundTile);

/// <summary>
/// <b>A level that makes sense to PLAY, generated — a floor plan and the
/// records on it, not a field of random tiles.</b>
/// </summary>
/// <remarks>
/// <para>
/// A blank project is 2,048 cells of tile 0 and a designer's first hour
/// goes on the scaffolding every level needs before any of it is a level:
/// floors she can stand on, a way down from each one to the next, and
/// enough records that the engine's own machinery — the bake, the patrol,
/// the door — has something to do. This writes that, for any of the three
/// shapes (CLAUDE.md 8.3), and then it is a starting point to paint over.
/// </para>
/// <para>
/// <b>THE ROLES COME OFF THE FLAGS AND NEVER OFF THE NAMES.</b> Which tile
/// is a floor is what <c>TileFlags</c> says about it, because that is the
/// only statement of what a cell DOES anywhere in this repository
/// (<see cref="Assets.LevelFlagSeeds"/>) — and the one lesson the asset
/// import already paid for is that guessing from the art gets the common
/// cases backwards (CLAUDE.md 11 step 7: the best pixel-count threshold
/// still calls twelve of level 1's forty-one tiles wrong). A project whose
/// flag table has no floor in it is REFUSED with the role it is missing
/// named, rather than handed a level of scenery that looks right and
/// cannot be walked on.
/// </para>
/// <para>
/// <b>And every number in the plan is one the engine already fixed.</b>
/// The first floor is row 6 because her box is 64 lines and a floor above
/// it starts her with a negative Y; floors are 8 rows apart because that
/// is 128 world lines, which is the City's own roof-to-street drop and
/// costs 32 of her 100 points (CLAUDE.md 8.4); a hole is three tiles
/// because <c>BOX_SOLID_V</c> ORs every tile under her six-byte box and two
/// is a gap she can stand across (CLAUDE.md 8.8).
/// </para>
/// </remarks>
public static class LevelGenerator
{
    /// <summary>Her box is 64 lines, so a floor above this starts her off the map.</summary>
    public const int FirstFloor = 6;

    /// <summary>128 world lines between floors — the City's own drop.</summary>
    public const int FloorStep = 8;

    /// <summary>Three tiles, which is what BOX_SOLID_V makes a gap.</summary>
    public const int HoleTiles = 3;

    /// <summary>The patrol half-width every generated enemy gets, in tiles.</summary>
    public const int PatrolTiles = 3;

    /// <summary>
    /// Fill <paramref name="project"/> in. Returns what it made, or the
    /// reason it would not.
    /// </summary>
    public static (GeneratedLevel? Made, string? Refused) Fill(
        EditorProject project, Tileset tiles)
    {
        if (Role(project, tiles, f => f.HasFlag(TileFlags.Solid)
                                      && !f.HasFlag(TileFlags.Ladder)) is not { } floor)
            return (null, "no tile in this project is Solid, so there is nothing "
                        + "to stand on. Mark a floor tile Solid and generate again");
        if (Role(project, tiles, f => f.HasFlag(TileFlags.Ladder)
                                      && f.HasFlag(TileFlags.Platform)) is not { } ladder)
            return (null, "no tile in this project is Ladder and Platform. The top "
                        + "rung has to be a floor as well as a shaft or she can only "
                        + "fall onto it (CLAUDE.md 8.8), so a ladder needs both");
        if (Role(project, tiles, f => f == TileFlags.None) is not { } sky)
            return (null, "every tile in this project carries a flag, so there is "
                        + "nothing to use as background. The face of a building is "
                        + "scenery: made solid, the foot of every ladder is a place "
                        + "she arrives inside a wall (CLAUDE.md 8.8)");

        int w = project.Width, h = project.Height;
        var floors = new List<int>();
        for (var row = FirstFloor; row <= h - 2; row += FloorStep)
            floors.Add(row);
        if (floors.Count < 1)
            return (null, $"a {w}x{h} map has no room for a floor at row {FirstFloor}");

        // The ladder columns, spread across whatever width this is: four of
        // them on the City's 128 and three on a 32-wide shaft, and the gap
        // between two floors takes the next one round, so every floor has
        // to be WALKED before it can be left.
        var step = Math.Max(9, w / 4);
        var ladders = new List<int>();
        for (var x = 5; x <= w - 3; x += step)
            ladders.Add(x);

        Array.Fill(project.Map, sky.Index);
        project.Overlays.Clear();
        project.Entities.Clear();

        foreach (var row in floors)
            for (var x = 0; x < w; x++)
                project.Map[row * w + x] = floor.Index;
        for (var x = 0; x < w; x++)                 // ... and the ground itself
            project.Map[(h - 1) * w + x] = floor.Index;

        for (var i = 0; i + 1 < floors.Count; i++)
        {
            var x = ladders[i % ladders.Count];
            for (var row = floors[i]; row < floors[i + 1]; row++)
                project.Map[row * w + x] = ladder.Index;
        }

        // A HOLE GOES WHERE IT CANNOT CUT THE FLOOR IN TWO. A gap between
        // her and the ladder she has to reach is a level that stops being
        // playable at the second floor, so the hole is only cut where the
        // run of floor either side of it still joins every ladder on that
        // row - and if there is nowhere like that, the floor keeps its
        // skin. Nothing here is a judgement: the walk is checked.
        var holes = 0;
        for (var i = 1; i + 1 < floors.Count; i += 2)
        {
            var used = Used(ladders, floors, i);
            if (HolePlace(w, used) is not { } hx) continue;
            for (var x = hx; x < hx + HoleTiles; x++)
                project.Map[floors[i] * w + x] = sky.Index;
            holes++;
        }

        var made = Populate(project, floors, ladders, w);
        return (new GeneratedLevel(floors.Count, floors.Count - 1, holes,
                                   made.Pickups, made.Enemies,
                                   floor.Name, ladder.Name, sky.Name), null);
    }

    private readonly record struct Chosen(byte Index, string Name);

    private static Chosen? Role(EditorProject project, Tileset tiles,
                                Func<TileFlags, bool> want)
    {
        for (var i = 0; i < tiles.Count; i++)
        {
            var name = tiles[i].Name;
            project.TileFlags.TryGetValue(name, out var flags);
            if (want(flags)) return new Chosen((byte)i, name);
        }
        return null;
    }

    /// <summary>The ladder columns that reach floor <paramref name="i"/>.</summary>
    private static int[] Used(List<int> ladders, List<int> floors, int i) =>
        [ladders[(i - 1) % ladders.Count], ladders[i % ladders.Count]];

    /// <summary>
    /// The leftmost run of three tiles that leaves every ladder on the row
    /// on the SAME side of it, or nothing.
    /// </summary>
    private static int? HolePlace(int w, int[] used)
    {
        for (var x = 2; x + HoleTiles < w - 2; x++)
        {
            var left = used.Count(u => u < x);
            var right = used.Count(u => u >= x + HoleTiles);
            if (left + right != used.Length) continue;      // a hole ON a ladder
            if (left != 0 && right != 0) continue;          // ... or between two
            return x;
        }
        return null;
    }

    private static (int Pickups, int Enemies) Populate(
        EditorProject project, List<int> floors, List<int> ladders, int w)
    {
        var top = floors[0];
        var bottom = floors[^1];

        // SHE STARTS IN THE AIR ON PURPOSE, one row above the floor, which
        // is what make_city_map.py does: a 64-line box placed level with
        // the tiles starts INSIDE them, the landing snaps her a whole row
        // low and BOX_SOLID_H then refuses every step (CLAUDE.md 8.6).
        project.Entities.Add(new Entity(
            EntityKind.PlayerStart, (ushort)(2 * Entity.TileWidth),
            (ushort)(top * Entity.TileHeight - Entity.TileHeight),
            EntityFlags.Active, 0, 0));

        // The key on the first floor down and the door on the ground: the
        // level has an END, which is what CHECK_KEY_DOOR's ER_OPENED and
        // the FSM's GS_CLEAR are waiting for (CLAUDE.md 8.1).
        var pickups = 0;
        var spots = new[]
        {
            (Row: floors[Math.Min(1, floors.Count - 1)], Kind: PickupKind.Key, P1: (byte)0),
            (Row: floors[floors.Count / 2], Kind: PickupKind.Ammo, P1: (byte)14),
            (Row: floors[^1], Kind: PickupKind.Medkit, P1: (byte)0),
        };
        foreach (var (row, kind, p1) in spots.DistinctBy(s => s.Row))
        {
            project.Entities.Add(Entity.AtTile(
                EntityKind.Pickup, Clear(w, ladders, row == top ? 6 : w / 2), row,
                Entity.DefaultFlagsFor(EntityKind.Pickup), (byte)kind, p1));
            pickups++;
        }

        project.Entities.Add(Entity.AtTile(
            EntityKind.Door, w - 4, bottom, Entity.DefaultFlagsFor(EntityKind.Door),
            0, (byte)PickupKind.Key));

        // ONE ENEMY PER SCREEN, AND ON A SHAFT THAT MEANS ONE. ENEMY_PICK's
        // near test is ES_X against the view and nothing else, so two whose
        // patrols come within a screen of each other are one enemy and one
        // record that never spawns (CLAUDE.md 8.7). The validator refuses
        // it; this simply does not make one.
        var enemies = 0;
        var pitch = EngineLimits.ScreenTilesAcross + 2 * PatrolTiles + 2;
        for (var x = PatrolTiles + 2; x + PatrolTiles + 2 < w; x += pitch)
        {
            // It hovers 20 lines over a floor, which puts its box top 40
            // lines above the floor's surface and hers 64 - inside
            // EN_H_SIGHT, so it can see her and she can shoot back.
            // ... on the floors in the MIDDLE of the descent and not the
            // first one down: an enemy on the second floor is a level that
            // opens with a fight, and on a shaft of eight floors the first
            // one is thirty seconds in.
            var row = floors[(floors.Count / 2 + enemies) % floors.Count];
            project.Entities.Add(new Entity(
                EntityKind.Enemy, (ushort)(x * Entity.TileWidth),
                (ushort)(row * Entity.TileHeight - 20),
                EntityFlags.Active, (byte)EnemyKind.Drone, PatrolTiles));
            enemies++;
        }
        return (pickups, enemies);
    }

    /// <summary>A tile column near <paramref name="want"/> that is not a ladder.</summary>
    private static int Clear(int w, List<int> ladders, int want)
    {
        for (var d = 0; d < w; d++)
            foreach (var x in new[] { want + d, want - d })
                if (x >= 1 && x < w - 1 && !ladders.Contains(x)) return x;
        return 1;
    }
}
