namespace CpcLevelEditor.Domain;

/// <summary>
/// Mode 0 pixel packing: two pens to a byte, bits interleaved. This is the
/// one place the interleaving is written down on this side of the build, the
/// way <c>tools/cpclib.py</c> is on the Python side.
/// </summary>
/// <remarks>
/// <para>
/// Bit numbers on the right are the PEN NUMBER's bit weights (bit 0 = value
/// 1, bit 3 = value 8):
/// </para>
/// <code>
/// byte bit 7 -> left  pixel, pen bit 0      bit 6 -> right pixel, pen bit 0
/// byte bit 5 -> left  pixel, pen bit 2      bit 4 -> right pixel, pen bit 2
/// byte bit 3 -> left  pixel, pen bit 1      bit 2 -> right pixel, pen bit 1
/// byte bit 1 -> left  pixel, pen bit 3      bit 0 -> right pixel, pen bit 3
/// </code>
/// <para>
/// <b>plan.md 4.2 states this table with bits 0↔3 and 1↔2 swapped and is
/// wrong</b> — an exporter built from the plan's table produces scrambled
/// palette indices. This one is CLAUDE.md 6.3's, confirmed on the emulator
/// by poking single bits into screen RAM and reading the rendered colour
/// back. Every exporter in this project needs a round-trip unit test for
/// exactly that reason, and <c>Mode0RoundTripTests</c> is this one's.
/// </para>
/// </remarks>
public static class Mode0Layout
{
    // pen bit -> byte bit. The left pixel owns the odd byte bits and the
    // right pixel the even ones, which is also why a transparent left pixel
    // contributes a mask of &AA and not &F0.
    private static readonly int[] LeftBits = [7, 3, 5, 1];   // indexed by pen bit
    private static readonly int[] RightBits = [6, 2, 4, 0];

    /// <summary>The four byte bits belonging to the left pixel.</summary>
    public const byte MaskLeft = 0b10101010;

    /// <summary>... and to the right pixel.</summary>
    public const byte MaskRight = 0b01010101;

    /// <summary>Pack two pen numbers (0-15) into one Mode 0 byte.</summary>
    public static byte Encode(int left, int right)
    {
        ArgumentOutOfRangeException.ThrowIfGreaterThan((uint)left, 15u, nameof(left));
        ArgumentOutOfRangeException.ThrowIfGreaterThan((uint)right, 15u, nameof(right));
        var value = 0;
        for (var penBit = 0; penBit < 4; penBit++)
        {
            value |= ((left >> penBit) & 1) << LeftBits[penBit];
            value |= ((right >> penBit) & 1) << RightBits[penBit];
        }
        return (byte)value;
    }

    /// <summary>Unpack a Mode 0 byte back into (left pen, right pen).</summary>
    public static (byte Left, byte Right) Decode(byte value)
    {
        var left = 0;
        var right = 0;
        for (var penBit = 0; penBit < 4; penBit++)
        {
            left |= ((value >> LeftBits[penBit]) & 1) << penBit;
            right |= ((value >> RightBits[penBit]) & 1) << penBit;
        }
        return ((byte)left, (byte)right);
    }
}
