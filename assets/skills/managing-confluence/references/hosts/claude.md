# Claude Code adapter

Inspect Claude Code's currently connected tools before choosing a read route; a server listed in
the MaaS catalogue is not necessarily authenticated or loaded. If `nvidia-confluence` is active,
use it for supported reads. Otherwise use `nvidia-glean` for indexed prose discovery and
`confluence-cli` for exact page metadata, hierarchy, attachments, and exports.

Treat NVIDIA Confluence MCP access as read-only unless its live tool list proves otherwise.
Agent writes still use `~/myGit/crosslv/assets/aipim/confluence-update`.
