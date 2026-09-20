using System.IO.Compression;

namespace CpcLevelEditor.Assets;

/// <summary>
/// The artist's sheets, decoded to RGB — and decoded here rather than by a
/// library, because a library is a NuGet restore between this repository and
/// a build and the decoder is two hundred lines.
/// </summary>
/// <remarks>
/// <para>
/// <b>It supports exactly what the asset pack contains and refuses the
/// rest by name.</b> Counted over all 137 PNGs in <c>assets/</c>: 77 are
/// 8-bit truecolour (colour type 2), 58 are 8-bit palette (type 3) and
/// <b>2 are truecolour with alpha (type 6)</b> — the title's own render and
/// the deleted placeholder's sheet — with none interlaced and nothing at 16
/// bits. Everything else, greyscale and interlaced included, throws with
/// the header it found in the message. A decoder that guessed would return
/// a picture, and a wrong picture quantises to a plausible tileset.
/// </para>
/// <para>
/// <b>ALPHA IS DROPPED, WHICH IS WHAT THE PYTHON SIDE DOES TOO.</b>
/// <c>tools/cpclib.py</c>'s <c>quantise</c> converts to RGB before it looks
/// at a pixel, so a transparent pixel keeps its palette colour and is
/// quantised like any other. That is not an oversight in either place: for
/// a tile sheet, transparency is a TABLE and never a property of the pixels
/// (CLAUDE.md 7.3) — <c>tile_table.json</c> says which tiles are overlays,
/// and pen 0 is what carries it into the bytes.
/// </para>
/// </remarks>
public sealed class Png
{
    private const int BytesPerPixel = 3;

    private static ReadOnlySpan<byte> Signature => [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];

    public required int Width { get; init; }

    public required int Height { get; init; }

    /// <summary>Three bytes a pixel, row-major — R, G, B.</summary>
    public required byte[] Rgb { get; init; }

    public (byte R, byte G, byte B) At(int x, int y)
    {
        ArgumentOutOfRangeException.ThrowIfGreaterThanOrEqual((uint)x, (uint)Width);
        ArgumentOutOfRangeException.ThrowIfGreaterThanOrEqual((uint)y, (uint)Height);
        var at = (y * Width + x) * BytesPerPixel;
        return (Rgb[at], Rgb[at + 1], Rgb[at + 2]);
    }

    public static Png Load(string path) => Decode(File.ReadAllBytes(path), path);

    public static Png Decode(byte[] bytes, string what = "<png>")
    {
        if (bytes.Length < Signature.Length
            || !bytes.AsSpan(0, Signature.Length).SequenceEqual(Signature))
            throw new InvalidDataException($"{what}: not a PNG");

        int width = 0, height = 0, bitDepth = 0, colourType = 0, interlace = 0;
        byte[]? palette = null;
        var data = new MemoryStream();
        var seenHeader = false;

        for (var at = Signature.Length; at + 8 <= bytes.Length;)
        {
            var length = ReadUInt32(bytes, at);
            var type = System.Text.Encoding.ASCII.GetString(bytes, at + 4, 4);
            var body = at + 8;
            if (body + length + 4 > bytes.Length)
                throw new InvalidDataException($"{what}: chunk {type} runs past the file");

            switch (type)
            {
                case "IHDR":
                    width = (int)ReadUInt32(bytes, body);
                    height = (int)ReadUInt32(bytes, body + 4);
                    bitDepth = bytes[body + 8];
                    colourType = bytes[body + 9];
                    interlace = bytes[body + 12];
                    seenHeader = true;
                    break;
                case "PLTE":
                    palette = bytes[body..(body + (int)length)];
                    break;
                case "IDAT":
                    data.Write(bytes, body, (int)length);
                    break;
            }

            if (type == "IEND")
                break;
            at = body + (int)length + 4;
        }

        if (!seenHeader)
            throw new InvalidDataException($"{what}: no IHDR");
        if (bitDepth != 8 || interlace != 0 || colourType is not (2 or 3 or 6))
            throw new NotSupportedException(
                $"{what}: bit depth {bitDepth}, colour type {colourType}, interlace "
                + $"{interlace} — this decoder does 8-bit colour types 2, 3 and 6, "
                + "non-interlaced, which is every PNG in this project's asset pack");
        if (colourType == 3 && palette is null)
            throw new InvalidDataException($"{what}: colour type 3 with no PLTE");

        var samples = colourType switch { 2 => 3, 6 => 4, _ => 1 };
        var raw = Inflate(data.ToArray(), what);
        var unfiltered = Unfilter(raw, width, height, samples, what);

        var rgb = new byte[width * height * BytesPerPixel];
        for (var i = 0; i < width * height; i++)
        {
            var to = i * BytesPerPixel;
            if (colourType == 3)
            {
                var entry = unfiltered[i] * 3;
                if (entry + 2 >= palette!.Length)
                    throw new InvalidDataException($"{what}: palette index past PLTE");
                rgb[to] = palette[entry];
                rgb[to + 1] = palette[entry + 1];
                rgb[to + 2] = palette[entry + 2];
            }
            else
            {
                var from = i * samples;
                rgb[to] = unfiltered[from];
                rgb[to + 1] = unfiltered[from + 1];
                rgb[to + 2] = unfiltered[from + 2];
            }
        }

        return new Png { Width = width, Height = height, Rgb = rgb };
    }

    private static uint ReadUInt32(byte[] bytes, int at) =>
        ((uint)bytes[at] << 24) | ((uint)bytes[at + 1] << 16)
        | ((uint)bytes[at + 2] << 8) | bytes[at + 3];

    private static byte[] Inflate(byte[] zlib, string what)
    {
        try
        {
            using var source = new MemoryStream(zlib);
            using var stream = new ZLibStream(source, CompressionMode.Decompress);
            using var into = new MemoryStream();
            stream.CopyTo(into);
            return into.ToArray();
        }
        catch (InvalidDataException e)
        {
            throw new InvalidDataException($"{what}: the IDAT stream does not inflate", e);
        }
    }

    /// <summary>
    /// The five per-scanline filters of the PNG specification. Each line
    /// carries its filter type in a leading byte and predicts from the pixel
    /// to the LEFT, the one ABOVE, and the one above-left — so the lines have
    /// to be undone in order and the previous line kept.
    /// </summary>
    private static byte[] Unfilter(byte[] raw, int width, int height, int samples, string what)
    {
        var stride = width * samples;
        if (raw.Length < (stride + 1) * (long)height)
            throw new InvalidDataException(
                $"{what}: {raw.Length} inflated bytes for {height} lines of {stride}");

        var output = new byte[stride * height];
        var previous = new byte[stride];
        var at = 0;

        for (var y = 0; y < height; y++)
        {
            var filter = raw[at++];
            var line = output.AsSpan(y * stride, stride);
            raw.AsSpan(at, stride).CopyTo(line);
            at += stride;

            for (var x = 0; x < stride; x++)
            {
                int left = x >= samples ? line[x - samples] : 0;
                int up = previous[x];
                int upLeft = x >= samples ? previous[x - samples] : 0;
                line[x] = filter switch
                {
                    0 => line[x],
                    1 => (byte)(line[x] + left),
                    2 => (byte)(line[x] + up),
                    3 => (byte)(line[x] + (left + up) / 2),
                    4 => (byte)(line[x] + Paeth(left, up, upLeft)),
                    _ => throw new InvalidDataException(
                        $"{what}: line {y} has filter type {filter}"),
                };
            }

            line.CopyTo(previous);
        }

        return output;
    }

    private static int Paeth(int a, int b, int c)
    {
        var p = a + b - c;
        int pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c);
        if (pa <= pb && pa <= pc)
            return a;
        return pb <= pc ? b : c;
    }
}
