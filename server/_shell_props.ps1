
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$TagsJson = $null,
  [string]$RatingStars = $null,
  [switch]$ReadOnly
)
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class ShellProps {
  [StructLayout(LayoutKind.Sequential, Pack=4)]
  public struct PROPERTYKEY {
    public Guid fmtid;
    public uint pid;
  }

  [StructLayout(LayoutKind.Sequential)]
  public struct PROPVARIANT {
    public ushort vt;
    public ushort wReserved1;
    public ushort wReserved2;
    public ushort wReserved3;
    public IntPtr p;
    public int p2;
  }

  [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IPropertyStore {
    uint GetCount(out uint cProps);
    uint GetAt(uint iProp, out PROPERTYKEY pkey);
    uint GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
    uint SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
    uint Commit();
  }

  [DllImport("shell32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  public static extern void SHGetPropertyStoreFromParsingName(
    string pszPath, IntPtr pbc, uint flags, ref Guid riid, out IPropertyStore ppv);

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  public static extern void PSGetPropertyKeyFromName(string pszName, out PROPERTYKEY ppropkey);

  [DllImport("ole32.dll")]
  public static extern int PropVariantClear(ref PROPVARIANT pvar);

  public const ushort VT_EMPTY = 0;
  public const ushort VT_UI4 = 19;
  public const ushort VT_LPWSTR = 31;
  public const ushort VT_VECTOR = 0x1000;
  public const uint GPS_DEFAULT = 0;
  public const uint GPS_READWRITE = 2;

  public static readonly Guid IID_IPropertyStore = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");

  public static IPropertyStore Open(string path, bool write) {
    Guid iid = IID_IPropertyStore;
    IPropertyStore ps;
    SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, write ? GPS_READWRITE : GPS_DEFAULT, ref iid, out ps);
    return ps;
  }

  public static void SetKeywords(IPropertyStore ps, string[] tags) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Keywords", out key);
    PROPVARIANT pv = new PROPVARIANT();
    if (tags == null || tags.Length == 0) {
      pv.vt = VT_EMPTY;
    } else {
      // VT_VECTOR|VT_LPWSTR via PropVariant helper in managed form is awkward;
      // set as semicolon-joined System.Comment fallback handled elsewhere.
      // Use InitPropVariantFromStringAsVector via propsys if available.
      InitStringVector(tags, out pv);
    }
    ps.SetValue(ref key, ref pv);
    PropVariantClear(ref pv);
  }

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  private static extern void InitPropVariantFromStringAsVector(
    [MarshalAs(UnmanagedType.LPArray, ArraySubType=UnmanagedType.LPWStr)] string[] prgsz,
    uint cElems, out PROPVARIANT ppropvar);

  public static void InitStringVector(string[] tags, out PROPVARIANT pv) {
    InitPropVariantFromStringAsVector(tags, (uint)tags.Length, out pv);
  }

  public static void SetRating(IPropertyStore ps, uint rating) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Rating", out key);
    PROPVARIANT pv = new PROPVARIANT();
    if (rating == 0) {
      pv.vt = VT_EMPTY;
    } else {
      pv.vt = VT_UI4;
      pv.p = new IntPtr(rating);
    }
    ps.SetValue(ref key, ref pv);
    PropVariantClear(ref pv);
  }

  public static string[] GetKeywords(IPropertyStore ps) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Keywords", out key);
    PROPVARIANT pv;
    ps.GetValue(ref key, out pv);
    try {
      if (pv.vt == VT_EMPTY) return new string[0];
      // Best-effort: PropVariantToStringVector
      return PropVariantToStrings(ref pv);
    } finally {
      PropVariantClear(ref pv);
    }
  }

  [DllImport("propsys.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
  private static extern void PropVariantToStringVector(
    ref PROPVARIANT propvar,
    [Out, MarshalAs(UnmanagedType.LPArray, ArraySubType=UnmanagedType.LPWStr, SizeParamIndex=2)] out string[] prgsz,
    out uint pcElem);

  public static string[] PropVariantToStrings(ref PROPVARIANT pv) {
    try {
      string[] arr;
      uint n;
      PropVariantToStringVector(ref pv, out arr, out n);
      return arr ?? new string[0];
    } catch {
      return new string[0];
    }
  }

  public static uint GetRating(IPropertyStore ps) {
    PROPERTYKEY key;
    PSGetPropertyKeyFromName("System.Rating", out key);
    PROPVARIANT pv;
    ps.GetValue(ref key, out pv);
    try {
      if (pv.vt == VT_UI4) return (uint)pv.p.ToInt64();
      return 0;
    } finally {
      PropVariantClear(ref pv);
    }
  }
}
"@

if ($ReadOnly) {
  $ps = [ShellProps]::Open($Path, $false)
  $tags = [ShellProps]::GetKeywords($ps)
  $rating = [ShellProps]::GetRating($ps)
  $obj = @{ tags = @($tags); rating = [int]$rating }
  $obj | ConvertTo-Json -Compress
  exit 0
}

$ps = [ShellProps]::Open($Path, $true)
if ($null -ne $TagsJson -and $TagsJson -ne "") {
  $tagArr = @()
  if ($TagsJson -ne "[]") {
    $tagArr = @(ConvertFrom-Json $TagsJson)
  }
  [ShellProps]::SetKeywords($ps, [string[]]$tagArr)
}
if ($null -ne $RatingStars -and $RatingStars -ne "") {
  $stars = [int]$RatingStars
  $map = @{ 0 = 0; 1 = 1; 2 = 25; 3 = 50; 4 = 75; 5 = 99 }
  $r = 0
  if ($map.ContainsKey($stars)) { $r = [uint32]$map[$stars] }
  [ShellProps]::SetRating($ps, $r)
}
$ps.Commit()
Write-Output "OK"
