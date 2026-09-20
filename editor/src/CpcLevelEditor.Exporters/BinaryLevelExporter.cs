using System.Buffers.Binary;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Exporters;

/// <summary>
/// Writes <c>level_&lt;n&gt;.lvl</c> — docs/editor.md 9.2, and byte for byte
/// what <c>tools/make_level.py</c> writes today.
/// </summary>
/// <remarks>
/// <para>
/// The engine only validates the magic, the width, the height and the entity
/// count; everything else in the header is written for the editor's benefit
/// and for a future engine. That is not a licence to get it wrong — the
/// golden file is the whole point of building this before the UI — but it
/// does say which fields a broken build would show up in.
/// </para>
/// <para>
/// Four things about the layout are easy to get nearly right:
/// </para>
/// <list type="bullet">
/// <item>there is <b>no padding and no alignment anywhere</b>; the sections
/// are strictly concatenated;</item>
/// <item><c>SCROLL_H</c> is <b>zero</b>, so a horizontal level's flags byte
/// is <c>0x00</c>;</item>
/// <item>an empty section still gets a real offset, and with no links and no
/// regions both of those equal the <b>file's own length</b>;</item>
/// <item>the counts are lengths divided by the record size — 4 for a link,
/// <b>7</b> for a region, which is why a region must not be padded to 8.</item>
/// </list>
/// </remarks>
public sealed class BinaryLevelExporter
{
    /// <summary>The level's bytes, ready for the disc.</summary>
    public byte[] Write(Level level)
    {
        var problems = level.Problems().ToList();
        if (problems.Count > 0)
            throw new ArgumentException(
                "the level will not load: " + string.Join("; ", problems), nameof(level));

        var entities = new byte[level.Entities.Count * Entity.Stride];
        for (var i = 0; i < level.Entities.Count; i++)
            WriteEntity(level.Entities[i], entities.AsSpan(i * Entity.Stride));

        var links = new byte[level.Links.Count * Link.Stride];
        for (var i = 0; i < level.Links.Count; i++)
        {
            var link = level.Links[i];
            var at = i * Link.Stride;
            links[at] = link.Kind;
            links[at + 1] = link.Source;
            links[at + 2] = link.Target;
            links[at + 3] = link.Param;
        }

        var regions = new byte[level.Regions.Count * Region.Stride];
        for (var i = 0; i < level.Regions.Count; i++)
        {
            var region = level.Regions[i];
            var at = regions.AsSpan(i * Region.Stride);
            at[0] = region.Kind;
            BinaryPrimitives.WriteUInt16LittleEndian(at[1..], region.X);
            BinaryPrimitives.WriteUInt16LittleEndian(at[3..], region.Y);
            at[5] = region.Width;
            at[6] = region.Height;
        }

        var offMap = LevelFormat.HeaderBytes;
        var offEntities = offMap + level.Map.Length;
        var offLinks = offEntities + entities.Length;
        var offRegions = offLinks + links.Length;

        var file = new byte[offRegions + regions.Length];
        var header = file.AsSpan(0, LevelFormat.HeaderBytes);

        LevelFormat.Magic.CopyTo(header);
        header[LevelFormat.OffVersion] = LevelFormat.Version;
        header[LevelFormat.OffLevelId] = level.LevelId;
        header[LevelFormat.OffFlags] = FlagsOf(level);
        BinaryPrimitives.WriteUInt16LittleEndian(
            header[LevelFormat.OffWidth..], checked((ushort)level.Width));
        BinaryPrimitives.WriteUInt16LittleEndian(
            header[LevelFormat.OffHeight..], checked((ushort)level.Height));
        header[LevelFormat.OffTilesetId] = level.TilesetId;
        header[LevelFormat.OffEntityCount] = checked((byte)level.Entities.Count);
        header[LevelFormat.OffLinkCount] = checked((byte)level.Links.Count);
        header[LevelFormat.OffRegionCount] = checked((byte)level.Regions.Count);

        var offsets = header[LevelFormat.OffSectionOffsets..];
        foreach (var (i, value) in new[] { offMap, offEntities, offLinks, offRegions }.Index())
            BinaryPrimitives.WriteUInt16LittleEndian(offsets[(i * 2)..], checked((ushort)value));

        level.Map.CopyTo(file, offMap);
        entities.CopyTo(file, offEntities);
        links.CopyTo(file, offLinks);
        regions.CopyTo(file, offRegions);
        return file;
    }

    private static byte FlagsOf(Level level)
    {
        var flags = (byte)level.Scroll;              // Horizontal is 0, and stays 0
        if (level.Underwater)
            flags |= LevelFormat.FlagUnderwater;
        return flags;                                // never FlagMapIsRle
    }

    private static void WriteEntity(Entity entity, Span<byte> at)
    {
        at[0] = (byte)entity.Kind;
        BinaryPrimitives.WriteUInt16LittleEndian(at[1..], entity.X);
        BinaryPrimitives.WriteUInt16LittleEndian(at[3..], entity.Y);
        at[5] = (byte)entity.Flags;
        at[6] = entity.P0;
        at[7] = entity.P1;
    }
}
