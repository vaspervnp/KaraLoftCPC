using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// What the ENGINE will make of a level, as against what the FORMAT will
/// carry — and every rule here is a place where the Z80 tests a byte,
/// quietly does nothing when it does not like it, and carries on.
/// </summary>
/// <remarks>
/// <para>
/// That is the right behaviour down there: a level the engine cannot read
/// should lose a record and not the frame (CLAUDE.md 8.7). It is also why a
/// designer has to be told up here, because nothing on the hardware says
/// which record was skipped — the level loads, the picture is right, and one
/// thing is missing.
/// </para>
/// <para>
/// <b>These were written after a level the editor exported HUNG a 6128.</b>
/// A pickup whose <c>p0</c> is <c>Book</c> is hudicon's cel 7, second from
/// last in its blob, and <c>ENT_FRAME_COPY</c> ran off the end of it — a
/// fault in the engine, fixed there, with <c>tools/test_entities.py</c>
/// now baking all six kinds. What the measurement also showed is how much
/// of a level's correctness the editor was not checking at all, and this is
/// that half.
/// </para>
/// </remarks>
public class EngineRuleTests
{
    private static bool Fires(EditorProject project, string rule, Severity severity)
    {
        var tiles = CitySource.ArtistTiles(project);
        return LevelValidator.Check(project, tiles)
            .Any(f => f.Rule == rule && f.Severity == severity);
    }

    /// <summary>
    /// Every rule below with the fault taken back out, in one place: the
    /// shipped City is a level the engine plays on real hardware, so
    /// anything that fires on it is the validator being wrong rather than
    /// the level.
    /// </summary>
    [Theory]
    [InlineData("pickup-budget")]
    [InlineData("pickup-touch")]
    [InlineData("pickup-grid")]
    [InlineData("pickup-kind")]
    [InlineData("enemy-kind")]
    [InlineData("enemy-spacing")]
    [InlineData("touch-not-pickup")]
    public void The_shipped_city_breaks_none_of_them(string rule)
    {
        var project = CitySource.Open();
        var tiles = CitySource.ArtistTiles(project);
        Assert.DoesNotContain(LevelValidator.Check(project, tiles), f => f.Rule == rule);
    }

    /// <summary>
    /// <c>ENT_BAKE_MAX</c> is 16 and <c>ENT_MAX</c> is 24, so a level can
    /// hold eight pickups the engine will not draw — and the AABB never
    /// consults the bake, so they are still there to walk into.
    /// </summary>
    [Fact]
    public void More_pickups_than_scratch_tiles()
    {
        var project = CitySource.Open();
        var tiles = CitySource.ArtistTiles(project);
        var already = project.Entities.Count(e => e.Kind == EntityKind.Pickup);

        // Up to the ceiling, and it is still a level the engine can draw.
        for (var i = already; i < EngineLimits.BakedPickups; i++)
            project.Entities.Add(Entity.AtTile(EntityKind.Pickup, 2 + i, 6,
                Entity.DefaultFlagsFor(EntityKind.Pickup)));
        Assert.Equal(EngineLimits.BakedPickups,
            project.Entities.Count(e => e.Kind == EntityKind.Pickup));
        Assert.DoesNotContain(LevelValidator.Check(project, tiles),
            f => f.Rule == "pickup-budget");

        // ... and one more is one the machine cannot show.
        project.Entities.Add(Entity.AtTile(EntityKind.Pickup, 60, 6,
            Entity.DefaultFlagsFor(EntityKind.Pickup)));
        Assert.True(Fires(project, "pickup-budget", Severity.Error));

        // AND IT IS NOT ENT_MAX DOING IT: the table still has room.
        Assert.True(project.Entities.Count < EngineLimits.MaxEntities);
        Assert.DoesNotContain(LevelValidator.Check(project, tiles),
            f => f.Rule == "engine-limits");
    }

    /// <summary>
    /// <c>ENT_ON_TOUCH</c> is the only handler that takes a pickup, and it
    /// runs on the <c>EF_TOUCH</c> sweep. The interact pass has doors, NPCs
    /// and receptacles in it and nothing else.
    /// </summary>
    [Fact]
    public void A_pickup_without_EF_TOUCH_can_never_be_taken()
    {
        var project = CitySource.Open();
        var i = project.Entities.FindIndex(e => e.Kind == EntityKind.Pickup);

        project.Entities[i] = project.Entities[i] with { Flags = EntityFlags.Active };
        Assert.True(Fires(project, "pickup-touch", Severity.Error));

        project.Entities[i] = project.Entities[i] with
        {
            Flags = EntityFlags.Active | EntityFlags.Touch,
        };
        Assert.False(Fires(project, "pickup-touch", Severity.Error));
    }

    /// <summary>
    /// The other way round: the touch sweep publishes the FIRST record whose
    /// box meets hers and stops, so something that is not a pickup can stand
    /// in front of one.
    /// </summary>
    [Fact]
    public void And_EF_TOUCH_on_anything_else_hides_what_is_under_it()
    {
        var project = CitySource.Open();
        var i = project.Entities.FindIndex(e => e.Kind == EntityKind.Door);

        project.Entities[i] = project.Entities[i] with
        {
            Flags = project.Entities[i].Flags | EntityFlags.Touch,
        };
        Assert.True(Fires(project, "touch-not-pickup", Severity.Warning));

        // A WARNING AND NOT AN ERROR, because the door still works: it is
        // opened from the interact pass, which this does not touch.
        Assert.False(Fires(project, "touch-not-pickup", Severity.Error));
    }

    /// <summary>
    /// <c>ENT_BAKE</c> stamps a pickup into the cell its TOP-LEFT falls in,
    /// and the box stays where the record says. Off the grid the two part.
    /// </summary>
    [Theory]
    [InlineData(1, 0)]                      // half a tile across
    [InlineData(0, 1)]                      // ... and a line down
    [InlineData(0, 8)]                      // half a tile down: a whole cell out
    public void A_pickup_off_the_tile_grid(int dx, int dy)
    {
        var project = CitySource.Open();
        var i = project.Entities.FindIndex(e => e.Kind == EntityKind.Pickup);
        var pickup = project.Entities[i];

        project.Entities[i] = pickup with
        {
            X = (ushort)(pickup.X + dx),
            Y = (ushort)(pickup.Y + dy),
        };
        Assert.True(Fires(project, "pickup-grid", Severity.Error));

        project.Entities[i] = pickup;
        Assert.False(Fires(project, "pickup-grid", Severity.Error));
    }

    /// <summary>
    /// <c>p0</c> is always "which thing this is", and both readers bound it
    /// against a table of their own: past the end, the record is in the file
    /// and the thing is not in the level.
    /// </summary>
    [Fact]
    public void A_p0_past_the_end_of_its_table()
    {
        var project = CitySource.Open();
        var pickup = project.Entities.FindIndex(e => e.Kind == EntityKind.Pickup);
        var enemy = project.Entities.FindIndex(e => e.Kind == EntityKind.Enemy);

        var kinds = (byte)Enum.GetValues<PickupKind>().Length;
        project.Entities[pickup] = project.Entities[pickup] with { P0 = kinds };
        Assert.True(Fires(project, "pickup-kind", Severity.Error));
        project.Entities[pickup] = project.Entities[pickup] with { P0 = (byte)(kinds - 1) };
        Assert.False(Fires(project, "pickup-kind", Severity.Error));

        var characters = (byte)Enum.GetValues<EnemyKind>().Length;
        project.Entities[enemy] = project.Entities[enemy] with { P0 = characters };
        Assert.True(Fires(project, "enemy-kind", Severity.Error));
        project.Entities[enemy] = project.Entities[enemy] with
        {
            P0 = (byte)EnemyKind.Drone,
        };
        Assert.False(Fires(project, "enemy-kind", Severity.Error));
    }

    /// <summary>
    /// <b>One enemy on screen at a time is a property of the LEVEL</b>, which
    /// is why <c>tools/make_city_map.py</c> asserts it and why the editor has
    /// to. <c>ENEMY_PICK</c> keeps the first it finds near the view, so the
    /// second is not a second enemy — it is no enemy.
    /// </summary>
    [Fact]
    public void Two_enemies_that_can_share_a_screen()
    {
        // THE CITY'S OWN THREE ARE TAKEN OUT AND TWO PUT BACK, because its
        // drones are 40 tiles apart across a 128-tile map and there is
        // nowhere left to put a fourth that clears both its neighbours -
        // which is the rule holding, not a reason to bend the test around
        // it.
        var project = CitySource.Open();
        var drone = project.Entities.First(e => e.Kind == EntityKind.Enemy);
        project.Entities.RemoveAll(e => e.Kind == EntityKind.Enemy);

        // Its beat is p1 tiles either side, so the next one has to start
        // more than a screen past where this one reaches.
        const int first = 10;
        var clear = first + drone.P1 + EngineLimits.ScreenTilesAcross + 1 + drone.P1;
        project.Entities.Add(drone with { X = (ushort)(first * Entity.TileWidth) });
        project.Entities.Add(drone with { X = (ushort)(clear * Entity.TileWidth) });
        Assert.False(Fires(project, "enemy-spacing", Severity.Error));

        // ... and one tile nearer is a drone that vanishes.
        project.Entities[^1] = drone with { X = (ushort)((clear - 1) * Entity.TileWidth) };
        Assert.True(Fires(project, "enemy-spacing", Severity.Error));

        // AND IT IS THE PATROL AND NOT THE PLACEMENT: standing still, the
        // same two positions are far enough apart.
        project.Entities[^2] = drone with
        {
            X = (ushort)(first * Entity.TileWidth),
            P1 = 0,
        };
        project.Entities[^1] = drone with
        {
            X = (ushort)((clear - 1) * Entity.TileWidth),
            P1 = 0,
        };
        Assert.False(Fires(project, "enemy-spacing", Severity.Error));
    }
}
