namespace CpcLevelEditor.Domain;

/// <summary>
/// What a tile DOES. One byte a tile, in the tileset's frame order, and it
/// travels in a sibling file — <c>tileflags_&lt;level&gt;.bin</c> — not
/// inside the <c>.lvl</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>THIS BIT ORDER IS THE ENGINE'S TOO.</b> <c>collide.asm</c>'s
/// <c>TA_*</c> used to run the other way up, with <c>TA_SOLID</c> at bit 7;
/// the engine took the format's numbering instead, so the file IS the table
/// <c>TILE_ATTR</c> holds and no exporter has to translate (CLAUDE.md 8.3).
/// </para>
/// <para>
/// This is independent of how a tile is DRAWN. <c>tile_table.json</c> says
/// opaque or overlay; <c>ladder</c> is an overlay in level 3 and an opaque
/// tile in level 1 with the same <see cref="Ladder"/> flag in both.
/// </para>
/// </remarks>
[Flags]
public enum TileFlags : byte
{
    None = 0,

    /// <summary>Blocks from every direction.</summary>
    Solid = 1,

    /// <summary>One-way — blocks a descent only. A ladder's top rung pairs this with <see cref="Ladder"/>.</summary>
    Platform = 2,

    /// <summary>Damages on contact.</summary>
    Hazard = 4,

    /// <summary>UP and DOWN move her along it.</summary>
    Ladder = 8,

    /// <summary>Reserved, level 4 — defined, never read.</summary>
    Water = 16,

    /// <summary>Reserved, level 5 — quicksand.</summary>
    Quicksand = 32,

    /// <summary>Reserved — a fall that does not end well.</summary>
    Deadly = 64,
}
