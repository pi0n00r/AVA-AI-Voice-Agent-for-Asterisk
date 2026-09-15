<!--
AI-NOTICE:Schema-Version=0.1
AI-NOTICE:License=AGPL-3.0-or-later
AI-NOTICE:Project=Ava
AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
AI-NOTICE:Scope=Fleet provenance bridge documentation
-->

# Upstream lineage

The maintained Bajaj branch is connected to the genuine upstream Git history
without rewriting or disguising the earlier reconstructed fleet history.

The provenance bridge commit has two parents:

- upstream AVA v7.5.4: `b2b521284d3d6a5126b58a5916de4ccdf4056c98`;
- accepted reconstructed fleet source: `92e848b2e6e364b0237a40790a91c7c3af752532`.

Its tree is exactly `cfd292d29799d209b8506ee9c21de3981cd15000`,
the accepted fleet source tree. Commit `7dcb5b1` remains the explicit point at
which that fleet history was reconstructed from a captured source tree. No
claim is made that the reconstructed root matches a particular upstream commit.

This bridge supplies a real common ancestor for future upstream merges while
preserving every historical fleet commit as a provenance parent. Upstream
updates after v7.5.4 must still be merged and qualified normally; ancestry does
not imply that later upstream releases have already been accepted.

