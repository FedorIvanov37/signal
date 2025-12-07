OUTPUT_FILE = "build/version_info.rc"

VERSION_INFO = r"""
1 VERSIONINFO
FILEVERSION 0,0,0,19
PRODUCTVERSION 0,0,0,19
FILEOS 0x40004
FILETYPE 0x1
{
BLOCK "StringFileInfo"
{
	BLOCK "040904B0"
	{
		VALUE "FileDescription", "ISO 8583 messages generation GUI/CLI"
		VALUE "InternalName", "signal.exe"
		VALUE "OriginalFilename", "signal.exe"
		VALUE "CompanyName", ""
		VALUE "LegalCopyright", "\xA9 Developed by Fedor Ivanov"
		VALUE "ProductName", "SIGNAL"
		VALUE "FileVersion", "v0.19.1"
		VALUE "ProductVersion", "v0.19.1"
	}
}

BLOCK "VarFileInfo"
{
	VALUE "Translation", 0x0409 0x04B0  
}
}   
"""

with open(OUTPUT_FILE, 'w') as output_file:
    output_file.write(VERSION_INFO)
