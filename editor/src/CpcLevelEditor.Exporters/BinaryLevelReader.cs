using System.Buffers.Binary;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Exporters;

/// <summary>
/// Reads <c>level_&lt;n&gt;.lvl</c> back into a <see cref="Level"/> — the
/// counterpart of <c>make_level.py</c>'s own <c>read()</c>, which exists for
/// the same reason: a format needs a reader that is not the writer turned
/// round, or a symmetrical mistake passes both ways.
/// </summary>
/// <remarks>
/// It reads the OFFSETS rather than recomputing them from the counts. The
/// writer derives one from the other, so a reader that did the same would
/// never notice a header whose offsets disagreed with its own sections.
/// </remarks>
public sealed class BinaryLevelReader
{
    public Level Read(ReadOnlySpan<byte> blob)
    {
        if (blob.Length < LevelFormat.HeaderBytes)
            throw new InvalidDataException(
                $"not a level: {blob.Length} bytes is shorter than the "
                + $"{LevelFormat.HeaderBytes}-byte header");

        if (!blob[..LevelFormat.Magic.Length].SequenceEqual(LevelFormat.Magic))
            throw new InvalidDataException("not a level: bad magic");

        var version = blob[LevelFormat.OffVersion];
        if (version != LevelFormat.Version)
            throw new InvalidDataException($"format version {version}, not {LevelFormat.Version}");

        var flags = blob[LevelFormat.OffFlags];
        if ((flags & LevelFormat.FlagMapIsRle) != 0)
            throw new InvalidDataException(
                "the header says the map is RLE and nothing on either side of this "
                + "build implements that");

        var width = BinaryPrimitives.ReadUInt16LittleEndian(blob[LevelFormat.OffWidth..]);
        var height = BinaryPrimitives.ReadUInt16LittleEndian(blob[LevelFormat.OffHeight..]);
        var entityCount = blob[LevelFormat.OffEntityCount];
        var linkCount = blob[LevelFormat.OffLinkCount];
        var regionCount = blob[LevelFormat.OffRegionCount];

        var offsets = blob[LevelFormat.OffSectionOffsets..];
        var offMap = BinaryPrimitives.ReadUInt16LittleEndian(offsets);
        var offEntities = BinaryPrimitives.ReadUInt16LittleEndian(offsets[2..]);
        var offLinks = BinaryPrimitives.ReadUInt16LittleEndian(offsets[4..]);
        var offRegions = BinaryPrimitives.ReadUInt16LittleEndian(offsets[6..]);

        Expect(offMap == LevelFormat.HeaderBytes, "the map does not start at the header's end");
        Expect(offEntities == offMap + width * height, "the entity section does not follow the map");
        Expect(offLinks == offEntities + entityCount * Entity.Stride,
               "the link section does not follow the entities");
        Expect(offRegions == offLinks + linkCount * Link.Stride,
               "the region section does not follow the links");
        Expect(blob.Length == offRegions + regionCount * Region.Stride,
               $"the file is {blob.Length} bytes and its own header accounts for "
               + $"{offRegions + regionCount * Region.Stride}");

        var entities = new Entity[entityCount];
        for (var i = 0; i < entityCount; i++)
        {
            var at = blob.Slice(offEntities + i * Entity.Stride, Entity.Stride);
            entities[i] = new Entity(
                (EntityKind)at[0],
                BinaryPrimitives.ReadUInt16LittleEndian(at[1..]),
                BinaryPrimitives.ReadUInt16LittleEndian(at[3..]),
                (EntityFlags)at[5],
                at[6], at[7]);
        }

        var links = new Link[linkCount];
        for (var i = 0; i < linkCount; i++)
        {
            var at = blob.Slice(offLinks + i * Link.Stride, Link.Stride);
            links[i] = new Link(at[0], at[1], at[2], at[3]);
        }

        var regions = new Region[regionCount];
        for (var i = 0; i < regionCount; i++)
        {
            var at = blob.Slice(offRegions + i * Region.Stride, Region.Stride);
            regions[i] = new Region(at[0],
                                    BinaryPrimitives.ReadUInt16LittleEndian(at[1..]),
                                    BinaryPrimitives.ReadUInt16LittleEndian(at[3..]),
                                    at[5], at[6]);
        }

        return new Level
        {
            LevelId = blob[LevelFormat.OffLevelId],
            TilesetId = blob[LevelFormat.OffTilesetId],
            Width = width,
            Height = height,
            Scroll = (ScrollAxis)(flags & 3),
            Underwater = (flags & LevelFormat.FlagUnderwater) != 0,
            Map = blob.Slice(offMap, width * height).ToArray(),
            Entities = entities,
            Links = links,
            Regions = regions,
        };
    }

    private static void Expect(bool ok, string what)
    {
        if (!ok)
            throw new InvalidDataException(what);
    }
}
