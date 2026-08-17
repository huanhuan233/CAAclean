CATIA V5R21 CAA win_b64 scripts
===================================

Copy these files to:

  D:\3Djiexi\3DjiexiCAA\tools\

Keep the existing x86 files:
  build_r21_x86.bat
  run_r21_x86.bat

The repository then has two architecture sets:
  x86 / intel_a:
    build_r21_x86.bat
    run_r21_x86.bat

  x64 / win_b64:
    build_r21_x64.bat
    run_r21_x64.bat

Before building, open Windows CMD and set roots to the directories
that directly contain the win_b64 folder:

  set "CAA_RADE_ROOT=D:\CATIA\Rade21"
  set "CAA_PREREQ_ROOT=D:\CATIA"
  set "RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE"

Check:
  dir "%CAA_RADE_ROOT%\win_b64\code\command\MkmkSetenv.bat"
  dir "%CAA_PREREQ_ROOT%\win_b64\code\bin\CNEXT.exe"

Build:
  cd /d D:\3Djiexi\3DjiexiCAA
  call tools\test_core_vs2008_x64.bat
  call tools\build_r21_x64.bat

Run self-test:
  call tools\run_r21_x64.bat --self-test

Run a CATPart:
  call tools\run_r21_x64.bat --input "D:\models\sample.CATPart" --output "D:\output\sample" --read-only --pretty

Expected executable:
  D:\3Djiexi\3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe

Expected build log:
  D:\3Djiexi\3DjiexiCAA\build_r21_x64.log

If vcvarsall.bat amd64 fails, modify the Visual Studio 2008 installation
and add Visual C++ x64 Compilers and Tools. Do not mix intel_a libraries
with win_b64 output.
