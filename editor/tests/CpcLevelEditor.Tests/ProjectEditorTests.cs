using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The edits, and the ones the engine could not be given.
/// </summary>
/// <remarks>
/// A designer finding out at export that the table holds 24 records has
/// already placed the 25th somewhere and has to find it again; these are the
/// rules applied on the stroke.
/// </remarks>
public class ProjectEditorTests
{
    private static EditorProject Empty() => new()
    {
        Id = "scratch",
        Name = "scratch",
        AssetLevel = "level1_city",
        Sheet = "city_tiles",
        Map = new byte[EngineLimits.MapWidth * EngineLimits.MapHeight],
    };

    private static Entity Standing(int tileX, int baseRow, EntityKind kind = EntityKind.Pickup) =>
        Entity.AtTile(kind, tileX, baseRow, Entity.DefaultFlagsFor(kind));

    /// <summary>
    /// <b>A designer places in tiles and the record carries world pixels</b>,
    /// with Y at the BASE of the hitbox — the line the thing stands on
    /// (CLAUDE.md 8.6). It is the same conversion <c>make_city_map.py</c>'s
    /// own <c>entity()</c> does, and the shipped key is the check: tile 24 of
    /// the roof's row comes out at (192,96).
    /// </summary>
    [Fact]
    public void An_entity_is_placed_in_tiles_and_stored_in_world_pixels()
    {
        var project = Empty();
        var outcome = ProjectEditor.Apply(project,
            [new EditOp("entity-add", Entity: Standing(24, 6))]);

        Assert.True(outcome.Ok);
        var placed = Assert.Single(project.Entities);
        Assert.Equal(192, placed.X);
        Assert.Equal(96, placed.Y);
        Assert.Equal(EntityFlags.Active | EntityFlags.Touch, placed.Flags);
    }

    /// <summary>
    /// <b>The table is ENT_MAX records and the engine clears exactly that
    /// many</b> (CLAUDE.md 8.6). The 25th is refused where it is made.
    /// </summary>
    [Fact]
    public void The_table_stops_at_ENT_MAX()
    {
        var project = Empty();
        var ops = Enumerable.Range(0, EngineLimits.MaxEntities + 1)
            .Select(i => new EditOp("entity-add", Entity: Standing(i, 6)))
            .ToArray();

        var outcome = ProjectEditor.Apply(project, ops);

        Assert.Equal(EngineLimits.MaxEntities, outcome.Applied);
        Assert.Contains("ENT_MAX", outcome.Rejected);
        Assert.Equal(EngineLimits.MaxEntities, project.Entities.Count);
    }

    [Fact]
    public void An_entity_off_the_world_is_refused()
    {
        var project = Empty();
        var outside = new Entity(EntityKind.Pickup,
            EngineLimits.MapWidth * Entity.TileWidth, 16, EntityFlags.Active, 0, 0);

        Assert.False(ProjectEditor.Apply(project, [new EditOp("entity-add", Entity: outside)]).Ok);
        Assert.Empty(project.Entities);

        // ... and the bottom line IS in: Y is the base of the hitbox, so a
        // thing standing on the floor below the last row is at exactly the
        // world's height.
        var lowest = new Entity(EntityKind.Pickup, 0,
            EngineLimits.MapHeight * Entity.TileHeight, EntityFlags.Active, 0, 0);
        Assert.True(ProjectEditor.Apply(project, [new EditOp("entity-add", Entity: lowest)]).Ok);
    }

    /// <summary>
    /// <b>A region is in TILES</b>, which is what its byte-wide width and
    /// height are for (<see cref="Region"/>) — so the map's own edge is what
    /// it is measured against.
    /// </summary>
    [Theory]
    [InlineData(120, 0, 8, 4, true)]
    [InlineData(126, 0, 8, 4, false)]       // runs off the right-hand edge
    [InlineData(0, 14, 4, 4, false)]        // ... and off the bottom
    [InlineData(0, 0, 0, 4, false)]         // covers nothing
    public void A_region_is_tiles_and_has_to_fit(int x, int y, int w, int h, bool allowed)
    {
        var project = Empty();
        var region = new Region(RegionKind.Water, (ushort)x, (ushort)y, (byte)w, (byte)h);

        var outcome = ProjectEditor.Apply(project, [new EditOp("region-add", Region: region)]);

        Assert.Equal(allowed, outcome.Ok);
        Assert.Equal(allowed ? 1 : 0, project.Regions.Count);
    }

    /// <summary>
    /// <b>An index means the list as the batch has it at that point.</b> The
    /// ops are applied in order and a client mutating its own copy in the
    /// same order sees the same indices, which is what lets an add, an edit
    /// of the thing just added and a removal of something else travel
    /// together.
    /// </summary>
    [Fact]
    public void An_index_means_the_list_as_the_batch_has_it()
    {
        var project = Empty();
        ProjectEditor.Apply(project, [
            new EditOp("entity-add", Entity: Standing(1, 6)),
            new EditOp("entity-add", Entity: Standing(2, 6)),
            new EditOp("entity-add", Entity: Standing(3, 6)),
        ]);

        var outcome = ProjectEditor.Apply(project, [
            new EditOp("entity-remove", Index: 0),
            // ... and 1 is now what 2 was
            new EditOp("entity-set", Index: 1, Entity: Standing(99, 6, EntityKind.Enemy)),
        ]);

        Assert.True(outcome.Ok);
        Assert.Equal([16, 99 * 8], project.Entities.Select(e => (int)e.X));
        Assert.Equal(EntityKind.Enemy, project.Entities[1].Kind);
    }

    [Fact]
    public void An_op_on_a_record_that_is_not_there_is_refused()
    {
        var project = Empty();
        ProjectEditor.Apply(project, [new EditOp("entity-add", Entity: Standing(1, 6))]);

        var outcome = ProjectEditor.Apply(project, [
            new EditOp("name", Name: "still applied"),
            new EditOp("entity-remove", Index: 7),
        ]);

        Assert.Equal(1, outcome.Applied);
        Assert.Contains("there is no entity 7", outcome.Rejected);
        Assert.Equal("still applied", project.Name);
        Assert.Single(project.Entities);
    }

    [Fact]
    public void There_is_no_such_edit()
    {
        var outcome = ProjectEditor.Apply(Empty(), [new EditOp("entity-fly")]);
        Assert.Contains("entity-fly", outcome.Rejected);
    }
}
