namespace CpcLevelEditor.Domain;

/// <summary>
/// One entity record: the eight bytes of docs/editor.md 9.2, which are also
/// the eight bytes <c>src/entity.asm</c> lays out in RAM, in that order, so
/// the engine's loader is an <c>LDIR</c> and not a conversion.
/// </summary>
/// <param name="Kind">Byte 0.</param>
/// <param name="X">
/// Bytes 1-2, u16 little-endian, <b>world pixels</b> — because a designer
/// thinks in pixels. Even ones are byte-aligned; a tile is 8 pixels wide,
/// so a tile column <c>c</c> is <c>c * 8</c>.
/// </param>
/// <param name="Y">
/// Bytes 3-4, u16 little-endian, world pixels at the <b>BASE</b> of the
/// hitbox — what a designer drops on a floor. The top is <c>Y - height</c>.
/// A tile is 16 pixels tall, so a tile row <c>r</c> is <c>r * 16</c>.
/// </param>
/// <param name="Flags">Byte 5.</param>
/// <param name="P0">Byte 6. See <see cref="Entity"/>'s remarks.</param>
/// <param name="P1">Byte 7.</param>
/// <remarks>
/// <para><b><c>p0</c> is always "which thing this is"</b> (CLAUDE.md 8.6):</para>
/// <list type="table">
///   <item><term>Pickup</term><description>p0 = <see cref="PickupKind"/>, p1 = amount, lock id, or symbol</description></item>
///   <item><term>Door</term><description>p0 = lock id, p1 = the <see cref="PickupKind"/> that opens it</description></item>
///   <item><term>Receptacle</term><description>p0 = the <see cref="PickupKind"/> it takes, p1 = how many it still wants</description></item>
///   <item><term>Npc</term><description>p0 = coins asked, p1 = which line he says</description></item>
///   <item><term>Enemy</term><description>p0 = which character (<c>EN_*</c>), p1 = patrol half-width in tiles</description></item>
///   <item><term>Hazard</term><description>p0 = damage, p1 = period</description></item>
/// </list>
/// <para>
/// <b>The Enemy row is the one with a stale comment against it.</b> The
/// header of <c>src/entity.asm</c> still says "p0 = patrol width, p1 = shots
/// a second"; CLAUDE.md 8.6 corrected that and says why — the rate, the
/// speed, the box, the art and the hit points come from the type table, so a
/// designer places a drone and not a set of numbers. <c>make_city_map.py</c>
/// writes <c>EN_DRONE</c> into p0 and reads p1 as the half-width, which is
/// what the shipped level does. Match the generator, not the comment.
/// </para>
/// </remarks>
public readonly record struct Entity(
    EntityKind Kind,
    ushort X,
    ushort Y,
    EntityFlags Flags,
    byte P0,
    byte P1)
{
    /// <summary>Bytes on disc and in RAM alike.</summary>
    public const int Stride = 8;

    /// <summary>Pixels across a tile — the map's own unit, horizontally.</summary>
    public const int TileWidth = 8;

    /// <summary>Pixels down a tile.</summary>
    public const int TileHeight = 16;

    /// <summary>
    /// A record placed the way a designer places one: in TILES, with the
    /// row being the one whose TOP surface the thing stands on. This is the
    /// conversion <c>make_city_map.py</c>'s own <c>entity()</c> does, kept
    /// here so no caller writes <c>* 8</c> and <c>* 16</c> by hand.
    /// </summary>
    public static Entity AtTile(EntityKind kind, int tileX, int baseRow,
                                EntityFlags flags, byte p0 = 0, byte p1 = 0)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(tileX);
        ArgumentOutOfRangeException.ThrowIfNegative(baseRow);
        return new Entity(kind,
                          checked((ushort)(tileX * TileWidth)),
                          checked((ushort)(baseRow * TileHeight)),
                          flags, p0, p1);
    }

    /// <summary>Whether the engine will sweep this slot at all.</summary>
    public bool IsActive => (Flags & EntityFlags.Active) != 0;
}
