namespace CpcLevelEditor.Domain;

/// <summary>
/// The editor's enum, in its declaration order — and it is the ENGINE's
/// order, because <c>src/entity.asm</c> copied it from docs/editor.md 5.3
/// rather than the other way round. A record's kind is one byte of the
/// eight and the engine indexes tables with it, so renumbering is a
/// format change.
/// </summary>
/// <remarks>
/// <c>PlayerStart</c> is ZERO, which is why an all-zero record is a real
/// entity at (0,0) and why <see cref="EntityFlags.Active"/> — not the kind
/// — decides whether a slot is in play (CLAUDE.md 8.6).
/// </remarks>
public enum EntityKind : byte
{
    PlayerStart = 0,
    Checkpoint = 1,
    Enemy = 2,
    Npc = 3,
    Pickup = 4,
    Hazard = 5,
    Door = 6,
    Receptacle = 7,
    Objective = 8,
    Transition = 9,
    Cutscene = 10,
}
