namespace CpcLevelEditor.Domain;

/// <summary>
/// Byte 5 of an entity record.
/// </summary>
/// <remarks>
/// <para>
/// <b>docs/editor.md 9.2 states this byte wrongly</b> — it says
/// "bit 0 αριστερά, bit 1 ενεργή από την αρχή", i.e. bit 0 = facing left.
/// The engine's <c>src/entity.asm</c> has bit 0 = <see cref="Active"/>, and
/// the shipped <c>level_1.lvl</c> agrees: its pickups carry 9
/// (<see cref="Active"/> | <see cref="Touch"/>), its door 5
/// (<see cref="Active"/> | <see cref="Solid"/>) and its NPC and drones 1.
/// CLAUDE.md wins over editor.md wherever they disagree, and here the file
/// on the disc settles it besides.
/// </para>
/// <para>
/// There is no facing bit. An enemy's facing is a run-time property the
/// engine works out from where she is (CLAUDE.md 8.7), not something a
/// designer places.
/// </para>
/// </remarks>
[Flags]
public enum EntityFlags : byte
{
    None = 0,

    /// <summary>In play at all. A slot without it is not swept.</summary>
    Active = 1,

    /// <summary>Picked up, opened, filled — done with.</summary>
    Taken = 2,

    /// <summary>A shut door: the physics must not pass it.</summary>
    Solid = 4,

    /// <summary>Acts on contact; without it, needs an UP press.</summary>
    Touch = 8,
}
