namespace CpcLevelEditor.Domain;

/// <summary>Four bytes: kind, source, target, param (docs/editor.md 9.2).</summary>
/// <remarks>
/// Nothing in the engine reads links yet — <c>MAP_INSTALL</c> parses the
/// magic, the shape, the entity count, the map and the records and stops.
/// The count and the offset are still written, and the section's record
/// size is what turns a byte length into a count, so it has to be right.
/// </remarks>
public readonly record struct Link(byte Kind, byte Source, byte Target, byte Param)
{
    public const int Stride = 4;
}
