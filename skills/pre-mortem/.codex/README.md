# Codex Adapter

This folder is the package-owned source for the Codex pre-mortem skill adapter.

Codex may not discover skills from this nested path automatically. Install or link this folder into the Codex skill directory:

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.codex\skills\pre-mortem" -Target "P:/packages/cc-skills-sdlc/skills/pre-mortem/.codex"
```

If junctions are not suitable, copy this folder instead and treat the copy as generated. The package-owned source remains authoritative.
