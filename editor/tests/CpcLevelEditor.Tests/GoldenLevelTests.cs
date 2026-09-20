using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// THE GOLDEN FILE, which is the whole reason the editor was built after the
/// engine and not before it (CLAUDE.md 11 step 7): there is a level the
/// engine already plays on real hardware, so the editor has something to be
/// correct against rather than being the first thing to test the format.
/// </summary>
public class GoldenLevelTests
{
    private static readonly BinaryLevelReader Reader = new();
    private static readonly BinaryLevelExporter Exporter = new();

    [Fact]
    public void The_file_round_trips_byte_for_byte()
    {
        var golden = Golden.Level1;
        var written = Exporter.Write(Reader.Read(golden));
        Assert.Equal(golden.Length, written.Length);
        Assert.Equal(golden, written);
    }

    [Fact]
    public void It_says_it_is_a_level()
    {
        var blob = Golden.Level1;
        Assert.Equal((byte)'L', blob[0]);
        Assert.Equal((byte)'V', blob[1]);
        Assert.Equal(LevelFormat.Version, blob[LevelFormat.OffVersion]);
    }

    [Fact]
    public void The_shape_is_the_engine_s()
    {
        var level = Reader.Read(Golden.Level1);
        Assert.Equal(EngineLimits.MapWidth, level.Width);
        Assert.Equal(EngineLimits.MapHeight, level.Height);
        Assert.Empty(level.Problems());
    }

    [Fact]
    public void The_flags_byte_is_zero_because_SCROLL_H_is_zero()
    {
        // The trap this catches: a writer that treats "horizontal" as a bit
        // to set rather than as the absence of one. It differs from the
        // shipped file in the header alone and nothing else would notice.
        Assert.Equal(0, Golden.Level1[LevelFormat.OffFlags]);
        var level = Reader.Read(Golden.Level1);
        Assert.Equal(ScrollAxis.Horizontal, level.Scroll);
        Assert.False(level.Underwater);
    }

    [Fact]
    public void The_map_section_IS_the_map()
    {
        var level = Reader.Read(Golden.Level1);
        Assert.Equal(Golden.Bytes(Golden.Build("city_map.bin")), level.Map);
    }

    [Fact]
    public void The_entity_section_is_the_live_records_in_RAM_s_own_layout()
    {
        var level = Reader.Read(Golden.Level1);
        var table = Golden.CityEntities;

        // The count in the header is the number of records the engine LDIRs,
        // and the file carries exactly that prefix of the 24-slot table.
        var live = Enumerable.Range(0, table.Length / Entity.Stride)
                             .Count(i => (table[i * Entity.Stride + 5] & 1) != 0);
        Assert.Equal(live, level.Entities.Count);
        Assert.Equal(table.Take(live * Entity.Stride),
                     Exporter.Write(level).Skip(LevelFormat.HeaderBytes + level.Map.Length));

        // ... and every one of them is active, because an inactive record
        // inside the count is not a gap: kind 0 is EK_PLAYER_START, so an
        // all-zero record is a real entity at (0,0).
        Assert.All(level.Entities, e => Assert.True(e.IsActive));
    }

    [Fact]
    public void The_pickups_and_the_door_carry_the_engine_s_flag_bits_not_editor_md_s()
    {
        // docs/editor.md 9.2 says bit 0 is "facing left" and bit 1 "active".
        // The file says otherwise and the engine agrees with the file.
        var level = Reader.Read(Golden.Level1);

        var pickups = level.Entities.Where(e => e.Kind == EntityKind.Pickup).ToList();
        Assert.Equal(5, pickups.Count);
        Assert.All(pickups, p =>
            Assert.Equal(EntityFlags.Active | EntityFlags.Touch, p.Flags));

        var door = Assert.Single(level.Entities, e => e.Kind == EntityKind.Door);
        Assert.Equal(EntityFlags.Active | EntityFlags.Solid, door.Flags);
        Assert.Equal((byte)PickupKind.Key, door.P1);        // p1 = what opens it

        Assert.All(level.Entities.Where(e => e.Kind is EntityKind.Enemy or EntityKind.Npc),
                   e => Assert.Equal(EntityFlags.Active, e.Flags));
    }

    [Fact]
    public void An_enemy_s_p0_is_which_character_and_p1_is_its_patrol_half_width()
    {
        // CLAUDE.md 8.6's rule - "p0 is always which thing this is" - against
        // the stale header comment in src/entity.asm, which still says
        // p0 = patrol width and p1 = shots a second. The shipped level is the
        // tie-breaker: three drones, all EN_DRONE = 1 in p0, with half-widths
        // of 4, 4 and 6 tiles in p1. Read the other way round it would be
        // three DIFFERENT characters patrolling one tile each.
        const byte EnDrone = 1;
        var enemies = Reader.Read(Golden.Level1).Entities
                            .Where(e => e.Kind == EntityKind.Enemy).ToList();
        Assert.Equal(3, enemies.Count);
        Assert.All(enemies, e => Assert.Equal(EnDrone, e.P0));
        Assert.Equal([4, 4, 6], enemies.Select(e => (int)e.P1));
    }

    [Fact]
    public void A_designer_places_in_tiles_and_the_record_holds_world_pixels()
    {
        // The key is on the roof at tile 24, and the roof's row is 6. Y is
        // the BASE of the hitbox - what a designer drops on a floor - so it
        // is the row's own top line, 96, which CLAUDE.md 8.8 names as the
        // surface she walks on.
        var level = Reader.Read(Golden.Level1);
        var key = Assert.Single(level.Entities,
            e => e.Kind == EntityKind.Pickup && e.P0 == (byte)PickupKind.Key);
        Assert.Equal(Entity.AtTile(EntityKind.Pickup, 24, 6,
                                   EntityFlags.Active | EntityFlags.Touch,
                                   (byte)PickupKind.Key), key);
        Assert.Equal(192, key.X);
        Assert.Equal(96, key.Y);
    }

    [Fact]
    public void Links_and_regions_are_counted_even_at_zero()
    {
        var blob = Golden.Level1;
        var level = Reader.Read(blob);
        Assert.Empty(level.Links);
        Assert.Empty(level.Regions);

        // An empty section still gets a real offset, and with both empty
        // those offsets are the file's own length.
        var offRegions = blob[LevelFormat.OffSectionOffsets + 6]
                       | blob[LevelFormat.OffSectionOffsets + 7] << 8;
        Assert.Equal(blob.Length, offRegions);
    }

    [Fact]
    public void A_changed_map_byte_breaks_the_round_trip()
    {
        // THE NEGATIVE CONTROL for the whole comparison. A test that says
        // "these bytes are equal" proves nothing until something shows that
        // it would have noticed them not being.
        var golden = Golden.Level1;
        var level = Reader.Read(golden);
        var tampered = (byte[])level.Map.Clone();
        tampered[1000] ^= 0xFF;

        var written = Exporter.Write(new Level
        {
            LevelId = level.LevelId,
            TilesetId = level.TilesetId,
            Width = level.Width,
            Height = level.Height,
            Scroll = level.Scroll,
            Underwater = level.Underwater,
            Map = tampered,
            Entities = level.Entities,
        });
        Assert.Equal(golden.Length, written.Length);
        Assert.NotEqual(golden, written);
    }

    [Fact]
    public void A_broken_magic_is_refused_the_way_MAP_INSTALL_refuses_it()
    {
        var blob = Golden.Level1;
        blob[0] = (byte)'X';
        Assert.Throws<InvalidDataException>(() => Reader.Read(blob));
    }

    [Fact]
    public void A_map_of_another_shape_will_not_be_written()
    {
        // MAP_CELL scales the row out of the base address at compile time,
        // so 128x16 is not a preference. tools/test_format.py pokes the
        // width to 64 and watches the loader leave MAP_ADDR zeroed; this is
        // the same rule one step earlier, where it costs nothing to catch.
        var level = Reader.Read(Golden.Level1);
        var narrow = new Level
        {
            LevelId = level.LevelId,
            TilesetId = level.TilesetId,
            Width = 64,
            Height = 16,
            Map = new byte[64 * 16],
            Entities = level.Entities,
        };
        var thrown = Assert.Throws<ArgumentException>(() => Exporter.Write(narrow));
        Assert.Contains("MAP_INSTALL refuses", thrown.Message);
    }
}
