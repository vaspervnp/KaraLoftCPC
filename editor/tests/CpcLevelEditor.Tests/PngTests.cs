using System.IO.Compression;
using System.Text.Json;
using CpcLevelEditor.Assets;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The decoder that is here instead of a package. Its real witness is
/// <see cref="AssetImportTests"/> — 41 tiles that come out as the shipped
/// blob byte for byte — and what this adds is the two things that comparison
/// cannot reach: the filters the sheets happen not to use, and the formats
/// the decoder must REFUSE rather than guess at.
/// </summary>
public class PngTests
{
    /// <summary>
    /// All five per-scanline filters of the specification, one to a line, on
    /// a picture whose pixels are known. A decoder that got Paeth wrong
    /// decodes most real images almost correctly, which is the failure mode
    /// worth buying a test for.
    /// </summary>
    [Fact]
    public void All_five_scanline_filters_round_trip()
    {
        const int width = 7, height = 5;
        var pixels = new byte[width * height * 3];
        for (var i = 0; i < pixels.Length; i++)
            pixels[i] = (byte)(i * 37 + (i % 5) * 11);      // busy enough to filter

        for (byte filter = 0; filter <= 4; filter++)
        {
            var decoded = Png.Decode(Truecolour(width, height, pixels, _ => filter));
            Assert.Equal(width, decoded.Width);
            Assert.Equal(pixels, decoded.Rgb);
        }

        // ... and mixed, which is what a real encoder writes
        Assert.Equal(pixels, Png.Decode(Truecolour(width, height, pixels, y => (byte)(y % 5))).Rgb);
    }

    /// <summary>
    /// <b>Alpha is dropped and the colour under it is kept</b>, which is what
    /// <c>tools/cpclib.py</c> does too: for a tile sheet, transparency is a
    /// TABLE and never a property of the pixels (CLAUDE.md 7.3).
    /// </summary>
    [Fact]
    public void Truecolour_with_alpha_keeps_the_colour_under_it()
    {
        var rgba = new byte[] { 200, 100, 50, 0, 1, 2, 3, 255 };
        var decoded = Png.Decode(Encode(2, 1, 6, [0, .. rgba]));

        Assert.Equal([200, 100, 50, 1, 2, 3], decoded.Rgb);
    }

    /// <summary>
    /// The formats the asset pack does not contain. A decoder that guessed
    /// would return a picture, and a wrong picture quantises to a plausible
    /// tileset — which is exactly the kind of failure this project's rule
    /// about negative controls exists for.
    /// </summary>
    [Fact]
    public void It_refuses_what_it_cannot_do_and_says_what_it_found()
    {
        var sixteenBit = Assert.Throws<NotSupportedException>(
            () => Png.Decode(Encode(1, 1, 2, [0, 0, 0, 0, 0, 0, 0], bitDepth: 16)));
        Assert.Contains("bit depth 16", sixteenBit.Message);

        var interlaced = Assert.Throws<NotSupportedException>(
            () => Png.Decode(Encode(1, 1, 2, [0, 1, 2, 3], interlace: 1)));
        Assert.Contains("interlace 1", interlaced.Message);

        var greyscale = Assert.Throws<NotSupportedException>(
            () => Png.Decode(Encode(1, 1, 0, [0, 9])));
        Assert.Contains("colour type 0", greyscale.Message);

        Assert.Throws<InvalidDataException>(() => Png.Decode([1, 2, 3, 4, 5, 6, 7, 8]));
    }

    /// <summary>
    /// Every sheet in the package, against the size Aseprite recorded in its
    /// own JSON — which is a second opinion about the picture from the tool
    /// that exported it.
    /// </summary>
    [Fact]
    public void Every_sheet_in_the_package_decodes_to_the_size_aseprite_recorded()
    {
        var sheets = Directory.GetFiles(
            Golden.Asset("sprites"), "*_sheet.png", SearchOption.AllDirectories);
        Assert.True(sheets.Length > 50, $"only {sheets.Length} sheets found");

        var checkedSizes = 0;
        foreach (var path in sheets)
        {
            var image = Png.Load(path);
            var json = Path.ChangeExtension(path, ".json");
            if (!File.Exists(json))
                continue;
            using var doc = JsonDocument.Parse(File.ReadAllText(json));
            var size = doc.RootElement.GetProperty("meta").GetProperty("size");
            Assert.Equal(size.GetProperty("w").GetInt32(), image.Width);
            Assert.Equal(size.GetProperty("h").GetInt32(), image.Height);
            checkedSizes++;
        }
        Assert.Equal(sheets.Length, checkedSizes);
    }

    // -----------------------------------------------------------------
    // A PNG writer, which exists only so the decoder can be handed one it
    // did not produce the bytes of.
    // -----------------------------------------------------------------

    private static byte[] Truecolour(int width, int height, byte[] rgb, Func<int, byte> filterOf)
    {
        var raw = new List<byte>();
        var stride = width * 3;
        for (var y = 0; y < height; y++)
        {
            var filter = filterOf(y);
            raw.Add(filter);
            for (var x = 0; x < stride; x++)
            {
                int here = rgb[y * stride + x];
                int left = x >= 3 ? rgb[y * stride + x - 3] : 0;
                int up = y > 0 ? rgb[(y - 1) * stride + x] : 0;
                int upLeft = x >= 3 && y > 0 ? rgb[(y - 1) * stride + x - 3] : 0;
                raw.Add((byte)(here - filter switch
                {
                    0 => 0,
                    1 => left,
                    2 => up,
                    3 => (left + up) / 2,
                    _ => Paeth(left, up, upLeft),
                }));
            }
        }
        return Encode(width, height, 2, [.. raw]);
    }

    private static int Paeth(int a, int b, int c)
    {
        var p = a + b - c;
        int pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c);
        if (pa <= pb && pa <= pc)
            return a;
        return pb <= pc ? b : c;
    }

    private static byte[] Encode(
        int width, int height, int colourType, byte[] filteredRaw,
        int bitDepth = 8, int interlace = 0)
    {
        var png = new List<byte> { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };

        var header = new List<byte>();
        header.AddRange(BigEndian(width));
        header.AddRange(BigEndian(height));
        header.AddRange([(byte)bitDepth, (byte)colourType, 0, 0, (byte)interlace]);
        Chunk(png, "IHDR", [.. header]);

        using var compressed = new MemoryStream();
        using (var deflate = new ZLibStream(compressed, CompressionLevel.Optimal, leaveOpen: true))
            deflate.Write(filteredRaw);
        Chunk(png, "IDAT", compressed.ToArray());
        Chunk(png, "IEND", []);
        return [.. png];
    }

    private static void Chunk(List<byte> png, string type, byte[] body)
    {
        png.AddRange(BigEndian(body.Length));
        var typed = new List<byte>(System.Text.Encoding.ASCII.GetBytes(type));
        typed.AddRange(body);
        png.AddRange(typed);
        png.AddRange(BigEndian((int)Crc32([.. typed])));
    }

    private static byte[] BigEndian(int value) =>
        [(byte)(value >> 24), (byte)(value >> 16), (byte)(value >> 8), (byte)value];

    private static uint Crc32(byte[] bytes)
    {
        var crc = 0xFFFFFFFFu;
        foreach (var b in bytes)
        {
            crc ^= b;
            for (var i = 0; i < 8; i++)
                crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
        }
        return crc ^ 0xFFFFFFFFu;
    }
}
