# Windows EXE build (GitHub Actions)

This repository includes a GitHub Actions workflow to produce a Windows .exe of the GUI using a Windows runner and PyInstaller.

How it works

- Workflow: `.github/workflows/build-windows.yml` runs on `windows-latest`.
- A helper script `.\scripts\ci_build_windows.ps1` installs dependencies and runs PyInstaller to produce a single-file EXE under `dist\`.
- The resulting EXE is uploaded as a workflow artifact named `mcp-windows-exe`.

Triggering the build

- Push to `main`, or
- From the repository Actions tab in GitHub, find the "Build Windows .exe" workflow and click "Run workflow".

Retrieving artifacts

- After the workflow completes, open the workflow run and download the `mcp-windows-exe` artifact.
 
Artifact notes

- The CI uploads the full `dist/` folder as the artifact (named `mcp-windows-dist`). This folder contains the EXE plus supporting DLLs and files.
- Because your app expects the SQLite DB to live next to the executable, include the `multi-agent_mcp_context_manager.db` alongside the EXE when you deploy or distribute the artifact.


Notes and tips

- The build runs PyInstaller with `--onefile --windowed`. If you want a consoleed EXE (for easier debugging), edit the script to remove `--windowed`.
- If your app expects runtime files (e.g. SQLite DB), consider packaging those with `--add-data` or shipping the EXE alongside your data files.
- For complex requirements (native libs), test the built EXE on a clean Windows VM.
- If you prefer to sign the EXE or produce an installer (MSI/NSIS), add an extra workflow step after artifact upload.

Troubleshooting

- If PyInstaller fails due to missing imports, check the spec file that PyInstaller generates in the repo root after a failed build and add hiddenimports via `--hidden-import` or by creating/adjusting the .spec file.
- GUI frameworks like Tkinter are supported by PyInstaller but may need explicit data inclusion (tk DLLs). If runtime errors show missing DLLs, collect those in the build script and add using `--add-data`.

If you'd like, I can:

- Add a .spec file tuned for this project (include the SQLite DB and other runtime files).
- Add a second workflow to produce a Windows installer (NSIS) and optionally sign the binary.

Spec file note

This repository includes a `mcp_gui.spec` PyInstaller spec that will be used by the CI build
if present. The spec attempts to bundle the `multi-agent_mcp_context_manager.db` (if it exists in
the repo root) and collects common hidden imports for `uvicorn`, `fastapi`, `websockets`, and `keyring`.
