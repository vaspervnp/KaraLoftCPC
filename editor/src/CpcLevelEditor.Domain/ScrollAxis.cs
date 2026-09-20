namespace CpcLevelEditor.Domain;

/// <summary>
/// Bits 0-1 of the header's flags byte.
/// </summary>
/// <remarks>
/// <b><see cref="Horizontal"/> is ZERO</b>, so a horizontally-scrolling
/// level's flags byte is <c>0x00</c> and not <c>0x01</c>. Level 1 is
/// horizontal, so its byte is zero and an exporter that "helpfully" set a
/// bit would differ from the shipped file in the header alone.
/// </remarks>
public enum ScrollAxis : byte
{
    Horizontal = 0,
    Vertical = 1,
}
