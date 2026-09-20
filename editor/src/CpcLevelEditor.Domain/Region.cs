namespace CpcLevelEditor.Domain;

/// <summary>Seven bytes: kind, x u16, y u16, w, h (docs/editor.md 9.2).</summary>
/// <remarks>
/// Seven, not eight — there is no padding anywhere in this format, and the
/// header's region count is <c>length / 7</c>. An exporter that aligned the
/// record to eight would report a count that is nearly right and a section
/// that is not.
/// </remarks>
public readonly record struct Region(byte Kind, ushort X, ushort Y, byte Width, byte Height)
{
    public const int Stride = 7;
}
