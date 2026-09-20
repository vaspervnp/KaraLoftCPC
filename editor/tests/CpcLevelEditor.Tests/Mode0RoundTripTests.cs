using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// CLAUDE.md 6.3: "every exporter needs a round-trip unit test (encode →
/// decode → original pens)". This is that test, and the reason it is not
/// ceremony is that <c>plan.md</c> 4.2 states the bit table with pen bits
/// 0↔3 and 1↔2 swapped — an exporter built from the plan assembles cleanly
/// and produces scrambled palette indices.
/// </summary>
public class Mode0RoundTripTests
{
    [Fact]
    public void Every_pen_pair_survives_encode_then_decode()
    {
        for (var left = 0; left < 16; left++)
        for (var right = 0; right < 16; right++)
        {
            var (back, backRight) = Mode0Layout.Decode(Mode0Layout.Encode(left, right));
            Assert.Equal((left, right), (back, backRight));
        }
    }

    [Fact]
    public void Every_byte_survives_decode_then_encode()
    {
        // The other direction, which is the one that matters for the baker:
        // it decodes the artist's tiles to pens, composites, and encodes
        // again. A table that lost a bit would show up here and nowhere else.
        for (var value = 0; value < 256; value++)
        {
            var (left, right) = Mode0Layout.Decode((byte)value);
            Assert.Equal((byte)value, Mode0Layout.Encode(left, right));
        }
    }

    [Theory]
    // pen bit -> byte bit, straight off CLAUDE.md 6.3's table. A pen of 1
    // is pen bit 0, a pen of 2 is bit 1, 4 is bit 2, 8 is bit 3.
    [InlineData(1, 7, 6)]
    [InlineData(2, 3, 2)]
    [InlineData(4, 5, 4)]
    [InlineData(8, 1, 0)]
    public void Each_pen_bit_lands_on_the_byte_bit_the_hardware_reads(
        int pen, int leftByteBit, int rightByteBit)
    {
        Assert.Equal(1 << leftByteBit, Mode0Layout.Encode(pen, 0));
        Assert.Equal(1 << rightByteBit, Mode0Layout.Encode(0, pen));
    }

    [Fact]
    public void The_left_pixel_owns_the_odd_bits_and_the_right_the_even_ones()
    {
        // Which is also why a transparent LEFT pixel contributes a mask of
        // &AA and not &F0 - the same fact the sprite blitter depends on.
        Assert.Equal(Mode0Layout.MaskLeft, Mode0Layout.Encode(15, 0));
        Assert.Equal(Mode0Layout.MaskRight, Mode0Layout.Encode(0, 15));
    }

    [Fact]
    public void The_plan_md_table_would_have_produced_different_bytes()
    {
        // THE NEGATIVE CONTROL. Both tables are self-consistent, so a
        // round-trip test passes under either one; what separates them is
        // the bytes they put on the screen. Over the city's real tiles the
        // two disagree on thousands of them, which is what says this suite
        // is checking the hardware's table and not merely an invertible one.
        var tiles = Golden.CityTiles;
        var differ = 0;
        foreach (var value in tiles)
        {
            var (left, right) = Mode0Layout.Decode(value);
            if (PlanMdEncode(left, right) != value)
                differ++;
        }
        Assert.True(differ > tiles.Length / 4,
            $"only {differ} of {tiles.Length} tile bytes distinguish CLAUDE.md 6.3's "
            + "table from plan.md 4.2's, so this suite is not pinning the right one");
    }

    /// <summary>plan.md 4.2's table: pen bits 0↔3 and 1↔2 swapped. Wrong, on purpose.</summary>
    private static byte PlanMdEncode(int left, int right)
    {
        int[] wrongLeft = [1, 5, 3, 7];     // pen bit -> byte bit
        int[] wrongRight = [0, 4, 2, 6];
        var value = 0;
        for (var penBit = 0; penBit < 4; penBit++)
        {
            value |= ((left >> penBit) & 1) << wrongLeft[penBit];
            value |= ((right >> penBit) & 1) << wrongRight[penBit];
        }
        return (byte)value;
    }
}
