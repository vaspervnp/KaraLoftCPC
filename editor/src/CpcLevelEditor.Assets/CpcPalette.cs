using System.Text.RegularExpressions;

namespace CpcLevelEditor.Assets;

/// <summary>
/// The gate array's 27 colours, and the sixteen of them this game programs.
/// </summary>
/// <remarks>
/// <para>
/// <b>ART IS QUANTISED AGAINST THE ENGINE'S PENS, NEVER AGAINST ITS OWN
/// IMAGE.</b> A sheet quantised against the colours it happens to contain
/// comes out looking right on its own and wrong over the level it is drawn
/// on, because the level programs sixteen pens and nothing renegotiates them
/// per sheet. So the palette is read from <c>src/palette.asm</c> — the
/// assembly the engine actually writes to <c>&amp;7F00</c> — exactly as
/// <c>tools/aseprite2spans.py</c>'s <c>game_palette</c> does it.
/// </para>
/// <para>
/// The RGB values are the ones <c>tools/cpclib.py</c> carries, read back off
/// the emulator rather than transcribed from a table in a book
/// (docs/cpc_palette.md).
/// </para>
/// </remarks>
public static partial class CpcPalette
{
    /// <summary>Pens the gate array has, and the hardware index each one takes.</summary>
    public const int PenCount = 16;

    /// <summary>Hardware colour index to RGB.</summary>
    public static readonly IReadOnlyDictionary<int, (byte R, byte G, byte B)> HardwareColours =
        new Dictionary<int, (byte, byte, byte)>
        {
            [20] = (0, 2, 1),     [4] = (0, 2, 107),    [21] = (12, 2, 244),
            [28] = (108, 2, 1),  [24] = (105, 2, 104),  [29] = (108, 2, 242),
            [12] = (243, 5, 6),   [5] = (240, 2, 104),  [13] = (243, 2, 244),
            [22] = (2, 120, 1),   [6] = (0, 120, 104),  [23] = (12, 123, 244),
            [30] = (110, 123, 1), [0] = (110, 125, 107),[31] = (110, 123, 246),
            [14] = (243, 125, 13),[7] = (243, 125, 107),[15] = (250, 128, 249),
            [18] = (2, 240, 1),   [2] = (0, 243, 107),  [19] = (15, 243, 242),
            [26] = (113, 245, 4),[25] = (113, 243, 107),[27] = (113, 243, 244),
            [10] = (243, 243, 13),[3] = (243, 243, 109),[11] = (255, 243, 249),
        };

    /// <summary>
    /// The sixteen pens the engine programs, as hardware colour indices, out
    /// of <c>PALETTE_DATA</c>. The seventeenth <c>db</c> is the border and is
    /// not a pen; the <c>&amp;40</c> the gate array wants on top of the index
    /// is stripped.
    /// </summary>
    public static int[] ReadGamePens(string paletteAsmPath)
    {
        var source = File.ReadAllText(paletteAsmPath);
        var start = source.IndexOf("PALETTE_DATA:", StringComparison.Ordinal);
        if (start < 0)
            throw new InvalidDataException($"{paletteAsmPath}: no PALETTE_DATA");
        var end = source.IndexOf("PEN_SOLID", start, StringComparison.Ordinal);
        var block = end < 0 ? source[start..] : source[start..end];

        var pens = PenByte().Matches(block)
            .Select(m => Convert.ToInt32(m.Groups[1].Value, 16) & 0x1F)
            .ToArray();
        if (pens.Length < PenCount)
            throw new InvalidDataException(
                $"{paletteAsmPath}: expected {PenCount} pens and a border, found {pens.Length}");
        foreach (var pen in pens[..PenCount])
            if (!HardwareColours.ContainsKey(pen))
                throw new InvalidDataException(
                    $"{paletteAsmPath}: hardware colour {pen} is not one of the 27");
        return pens[..PenCount];
    }

    /// <summary>
    /// The pen whose colour is nearest an RGB triple, by squared distance.
    /// <b>Ties go to the LOWEST pen</b>, which is what Python's
    /// <c>min(range(n), key=...)</c> does in <c>cpclib.nearest_in</c>; two
    /// implementations that disagree only on ties disagree on whole tiles.
    /// </summary>
    public static byte NearestPen(byte r, byte g, byte b, int[] pens)
    {
        var best = 0;
        var bestDistance = int.MaxValue;
        for (var pen = 0; pen < pens.Length; pen++)
        {
            var (pr, pg, pb) = HardwareColours[pens[pen]];
            var distance = (pr - r) * (pr - r) + (pg - g) * (pg - g) + (pb - b) * (pb - b);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = pen;
            }
        }
        return (byte)best;
    }

    /// <summary>Every pixel of a rectangle of <paramref name="image"/> as a pen, <c>[y][x]</c>.</summary>
    public static byte[][] Quantise(Png image, int x0, int y0, int width, int height, int[] pens)
    {
        var out_ = new byte[height][];
        for (var y = 0; y < height; y++)
        {
            out_[y] = new byte[width];
            for (var x = 0; x < width; x++)
            {
                var (r, g, b) = image.At(x0 + x, y0 + y);
                out_[y][x] = NearestPen(r, g, b, pens);
            }
        }
        return out_;
    }

    [GeneratedRegex(@"db\s+&([0-9A-Fa-f]{2})")]
    private static partial Regex PenByte();
}
