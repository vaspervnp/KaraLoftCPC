namespace CpcLevelEditor.Domain;

/// <summary>
/// What a pickup IS — <c>p0</c> on an <see cref="EntityKind.Pickup"/>
/// record, and <c>p1</c> on a <see cref="EntityKind.Door"/> (which pickup
/// opens it) or a <see cref="EntityKind.Receptacle"/> (which it takes).
/// </summary>
/// <remarks>
/// One list for every level, because a medkit is a medkit in all of them
/// and the handlers are shared (CLAUDE.md 8.6).
/// </remarks>
public enum PickupKind : byte
{
    Key = 0,
    Ammo = 1,
    Medkit = 2,
    Coin = 3,
    Idol = 4,

    /// <summary>
    /// A book of the cave's gate (CLAUDE.md 8.25): <c>p1</c> is its symbol's
    /// bit - sun 1, moon 2, eye 4, star 8 - and 128 more if it is CURSED,
    /// which costs her a cell and goes into no set. The gate is a
    /// <see cref="EntityKind.Receptacle"/> taking <c>Book</c> whose
    /// <c>p1</c> is the set of bits it wants, and it is the record right
    /// before its door.
    /// </summary>
    Book = 5,

    /// <summary>An oxygen tank: her air, full, in a level of water (CLAUDE.md 8.18).</summary>
    Oxygen = 6,
}
