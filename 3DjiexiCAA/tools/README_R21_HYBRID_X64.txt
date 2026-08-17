V5R21 hybrid host/target build
================================

This pack is for the common older V5R21 layout:

  RADE build tools (host):
    <RADE_ROOT>\intel_a\code\command

  CATIA/CAA prerequisite and runtime (target):
    <CATIA_ROOT>\win_b64

The RADE host tools being under intel_a does NOT by itself mean that
only a 32-bit target can be built. The target is selected by:

  _MkmkOS_BitMode=64

and the output is expected under:

  <workspace>\win_b64

Copy the three .bat files to:

  D:\3Djiexi\3DjiexiCAA\tools

Use Windows CMD:

  set "CAA_RADE_ROOT=D:\DassaultSystemes\T21"
  set "CAA_PREREQ_ROOT=D:\DassaultSystemes\B21"
  set "RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE"

  cd /d D:\3Djiexi\3DjiexiCAA

  call tools\probe_r21_x64_existing_env.bat
  call tools\build_r21_x64_host_intel_a.bat
  call tools\run_r21_x64_host_intel_a.bat --self-test

Expected x64 executable:

  D:\3Djiexi\3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe

Important failure meanings:

1. probe says VS2008 x64 compiler missing:
   Local x64 CAA compilation is not possible without that compiler.

2. mkGetPreq fails:
   The matching R21 CAA API prerequisite frameworks are missing or
   CAA_PREREQ_ROOT points to the wrong root. A working CATIA GUI alone
   is not enough.

3. LNK1112 X86 versus x64:
   At least one linked prerequisite is 32-bit. Do not force or copy it.
   Use a matching remote build environment.

4. Build passes but runtime DLL is missing:
   Check PATH and ensure CATIA/CAA target prerequisites are present in
   <CAA_PREREQ_ROOT>\win_b64.

Keep the existing x86/intel_a scripts. These new scripts do not modify them.
