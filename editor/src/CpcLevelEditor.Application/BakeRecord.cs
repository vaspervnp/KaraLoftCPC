using System.Text.Json;
using System.Text.Json.Serialization;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Application;

/// <summary>
/// The bake's own record — which (overlay, background) pair became which
/// tile — in the shape <c>build/city_baked.json</c> already has.
/// </summary>
/// <remarks>
/// <para>
/// <b>WITHOUT THIS FILE A LEVEL CANNOT BE OPENED AGAIN, ITS OWN AUTHOR'S
/// INCLUDED.</b> A map cell is one byte and a finished tile, so
/// <c>level_&lt;n&gt;.lvl</c> has nowhere to say "this cell is an overlay
/// over that one" (CLAUDE.md 7.3, 8.3); the pairing lives beside the level
/// or it does not live at all. <c>tools/make_city_map.py</c> writes one for
/// the level it generates and <see cref="LevelUnbaker"/> reads it, which is
/// how the shipped City opens in the editor — so an export that wrote the
/// three binaries and no record would produce a level the editor could
/// paint once and never re-open.
/// </para>
/// <para>
/// The names are the generator's, lower case, so the two files are
/// interchangeable: the editor can open what the build baked and the build's
/// own suite can read what the editor exported.
/// </para>
/// </remarks>
public static class BakeRecord
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
    };

    /// <summary>
    /// <c>city_tiles</c> → <c>city_baked.json</c>, which is the name the
    /// build already uses for level 1.
    /// </summary>
    public static string FileName(string sheet) =>
        sheet.Replace("_tiles", "", StringComparison.Ordinal) + "_baked.json";

    public static string Write(IReadOnlyList<BakedPair> pairs) =>
        JsonSerializer.Serialize(
            pairs.Select(p => new Record(p.Index, p.Over, p.Under, p.Name, p.Baked)), Options);

    public static IReadOnlyList<BakedPair> Read(string json) =>
        [.. (JsonSerializer.Deserialize<List<Record>>(json, Options)
             ?? throw new InvalidDataException("the bake record is empty"))
            .Select(r => new BakedPair(r.Index, r.Over, r.Under, r.Name, r.Baked))];

    private sealed record Record(
        [property: JsonPropertyName("index")] int Index,
        [property: JsonPropertyName("over")] int Over,
        [property: JsonPropertyName("under")] int Under,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("baked")] bool Baked);
}
