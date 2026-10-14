# Windows signing setup

The signed preview workflow is manual, restricted to reviewed `main`, uses the `windows-signing` GitHub environment and does not publish a release automatically. Existing unsigned build workflows are not evidence that signed distribution works.

## Publisher setup required

1. Follow Microsoft's Artifact Signing quickstart: https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart . Check individual/organization and country eligibility before creating paid resources. The owner must complete billing/account terms and identity validation personally.
2. Create a Public Trust certificate profile after identity validation. Record the exact certificate subject distinguished name, signing endpoint, account name and profile name.
3. Configure GitHub OIDC federation for the repository's `windows-signing` environment and grant the signing identity only the Artifact Signing Certificate Profile Signer role for that profile. Protect the environment with owner approval and main-only deployment restrictions. Instructions: https://github.com/Azure/artifact-signing-action/blob/main/docs/OIDC.md . No certificate private key or long-lived Azure client secret belongs in this repository.
4. Set environment variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `SIGNING_ENDPOINT`, `SIGNING_ACCOUNT`, `SIGNING_PROFILE`, `SIGNING_PUBLISHER`. Publisher must be the exact certificate subject, not a display-name substring.
5. After reviewed workflow changes reach main, run **Signed Windows preview**. It builds/tests source, signs backend EXE/DLL/PYD files, packages and signs the desktop binaries, constructs and signs the installer, verifies each publisher/signature/timestamp, and runs the existing installer smoke check. Only successful runs upload the signed candidate and evidence.
6. Test that exact signed installer on a clean Windows machine and on the affected owner's machine with Smart App Control still enabled. Verify startup, preserved data, restart and update. Record hashes after signing; a signature changes the bytes. A successful GitHub run does not establish local policy acceptance.

The signable backend uses `KINGDOM_BACKEND_LAYOUT=onedir` on Windows. This keeps the existing launcher path `desktop/bin/kingdom-backend.exe` while exposing native libraries for signing. The default unsigned build remains one-file. Do not distribute the backend EXE by itself from a directory build; its accompanying libraries are required.

## Free signing eligibility

Kingdom currently uses a custom non-commercial license. SignPath Foundation requires an OSI-approved open-source license without commercial dual licensing: https://signpath.org/terms . The current license therefore does not qualify. Do not relicense the project merely to obtain a certificate; that is an owner decision.

## Current status

The workflow and fail-closed verifier are implemented. Publisher account, identity validation, certificate profile and OIDC configuration are external prerequisites. No trusted signature has been issued, no signing account was purchased/created, and no App Control policy was changed. Actual signed build and installation remain unverified until those prerequisites are supplied.
