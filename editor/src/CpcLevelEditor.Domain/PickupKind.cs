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

    /// <summary>The book of level 3's puzzle; <c>p1</c> carries which symbol.</summary>
    Book = 5,
}
