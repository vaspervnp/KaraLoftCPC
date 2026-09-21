namespace CpcLevelEditor.Domain;

/// <summary>
/// What a region IS — byte 0 of the seven, in docs/editor.md 5.5's own
/// order.
/// </summary>
/// <remarks>
/// <b>NOTHING IN THE ENGINE READS REGIONS YET</b> — <c>MAP_INSTALL</c> parses
/// the magic, the shape, the entity count, the map and the records and
/// stops, and the shipped City has none. So this numbering is the EDITOR's
/// statement rather than something measured off a file, and it is written
/// here so that whatever reads it first has one place to agree with. The
/// same is true of <see cref="Link"/>.
/// </remarks>
public enum RegionKind : byte
{
    /// <summary>Level 4: buoyancy and the oxygen clock.</summary>
    Water = 0,

    /// <summary>Level 5: she sinks at the region's own rate.</summary>
    Quicksand = 1,

    /// <summary>Level 4 again: somewhere to breathe.</summary>
    OxygenVent = 2,

    /// <summary>A depth band, for placement rules rather than for play.</summary>
    Band = 3,

    /// <summary>The camera stops following her inside it.</summary>
    CameraLock = 4,

    /// <summary>She crosses it and something starts: the quake, the siphon.</summary>
    Trigger = 5,
}
