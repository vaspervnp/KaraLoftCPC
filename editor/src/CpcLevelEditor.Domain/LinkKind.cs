namespace CpcLevelEditor.Domain;

/// <summary>
/// What a <see cref="Link"/> IS — its first byte, in docs/editor.md 5.4's
/// own order.
/// </summary>
/// <remarks>
/// <b>One of them has a reader now, and it is the second.</b>
/// <c>PLACE_STATUE</c> walks the level's links when an altar is given its
/// idol and marks the target of every <see cref="Disables"/> whose source is
/// that altar (<c>src/hazard.asm</c>, CLAUDE.md 8.17); the engine's
/// <c>LK_DISABLES</c> is this value and <c>tools/test_forest7.py</c> holds
/// the two together. The others are the editor's statement, written down so
/// that whatever reads them first has one place to agree with.
/// </remarks>
public enum LinkKind : byte
{
    /// <summary>Pickup → Door: a key and the garage it opens.</summary>
    Unlocks = 0,

    /// <summary>Receptacle → Hazard: the altar and the trap its idol stops.</summary>
    Disables = 1,

    /// <summary>Receptacle × N → Door: the cave's book slots and the gate.</summary>
    RequiresAll = 2,

    /// <summary>Npc → Door: the nomad who sells the shelter's code.</summary>
    Reveals = 3,

    /// <summary>Objective → Pickup / Cutscene.</summary>
    Activates = 4,

    /// <summary>Hazard ↔ Hazard: one timing and phase for a group.</summary>
    SyncGroup = 5,
}
