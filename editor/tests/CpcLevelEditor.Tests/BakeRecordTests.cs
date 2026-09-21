using CpcLevelEditor.Application;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The fourth file, and why an export without it is a level that can be
/// painted once.
/// </summary>
/// <remarks>
/// A map cell is a finished tile and the format has nowhere to say which
/// cells were an overlay on a wall (CLAUDE.md 7.3, 8.3), so the pairing
/// lives beside the level or it does not live at all. The build has written
/// one since the bake existed — <c>build/city_baked.json</c> — and these
/// check that the editor reads that one and writes the same thing.
/// </remarks>
public class BakeRecordTests
{
    /// <summary>
    /// <b>The generator's record and the editor's are one file format.</b>
    /// It is what lets the shipped City open in the editor at all, and what
    /// lets the editor's own export be opened by anything that can open the
    /// shipped one.
    /// </summary>
    [Fact]
    public void The_record_the_build_writes_is_the_one_the_editor_reads()
    {
        var pairs = BakeRecord.Read(File.ReadAllText(Golden.Build("city_baked.json")));

        Assert.Equal(
            [.. Golden.CityBaked.Select(r =>
                new BakedPair(r.Index, r.Over, r.Under, r.Name, r.Baked))],
            pairs);

        // ... and back out again unchanged, which is the half that says the
        // editor's own file can be read by the same code.
        Assert.Equal(pairs, BakeRecord.Read(BakeRecord.Write(pairs)));
    }

    /// <summary>
    /// <b>AN EXPORT IS A FIXED POINT OF ITS OWN OPEN.</b> Export the City,
    /// open what came out as if it were a shipped level, and export that:
    /// all four files byte for byte. The numbering is the painter's both
    /// times, which is the part the shipped comparison cannot show —
    /// <see cref="ProjectTests.The_shipped_city_taken_apart_and_put_back_IS_the_same_picture"/>
    /// compares a picture precisely because the two numberings differ.
    /// </summary>
    [Fact]
    public void An_export_opens_again_and_exports_to_itself()
    {
        var root = CitySource.TemporaryRoot();
        try
        {
            var city = CitySource.Open();
            var first = ProjectExporter.WriteTo(
                root, city, ProjectExporter.Export(city, CitySource.ArtistTiles(city)));

            var again = ShippedLevel.Open(
                new ShippedLevel.Request { Id = "again", Name = "again", From = root },
                CitySource.Catalogue());
            var second = ProjectExporter.Files(
                again, ProjectExporter.Export(again, CitySource.ArtistTiles(again)));

            Assert.Equal(first.Select(f => f.Name), second.Select(f => f.Name));
            foreach (var (a, b) in first.Zip(second))
                Assert.Equal(a.Bytes, b.Bytes);

            // ... and it really did come off the disk, overlay layer and all
            Assert.NotEmpty(again.Overlays);
            Assert.Equal(city.Overlays.Count, again.Overlays.Count);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    /// <summary>
    /// The control: without the record, the composited cells are tile
    /// indices nothing can account for, and the un-bake says so rather than
    /// handing back a level with 51 flat tiles in it.
    /// </summary>
    [Fact]
    public void And_without_the_record_the_level_cannot_be_opened()
    {
        var root = CitySource.TemporaryRoot();
        try
        {
            var city = CitySource.Open();
            ProjectExporter.WriteTo(
                root, city, ProjectExporter.Export(city, CitySource.ArtistTiles(city)));
            File.WriteAllText(Path.Combine(root, "city_baked.json"), "[]");

            var thrown = Assert.Throws<InvalidDataException>(() => ShippedLevel.Open(
                new ShippedLevel.Request { Id = "flat", Name = "flat", From = root },
                CitySource.Catalogue()));
            Assert.Contains("bake record", thrown.Message);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
