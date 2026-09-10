# Packet integrity disclosure

The embedded report bodies were copied exactly as received between their sentinel lines,
excluding the single delimiter newline before each end sentinel.

| Packet | Original expected bytes | Received bytes | Original expected SHA-256 | Received SHA-256 | Result |
| --- | ---: | ---: | --- | --- | --- |
| 01 | 35,239 | 35,199 | `7e36af382212656ff4fae37a8c5112958864cc55d99f0a29959ab8f913eb36af` | `f641a3eb244326fa2b45ea462170d6bf1938541a1981f3ddb8029b6a6404f569` | MISMATCH, proceed under coordinator ruling |
| 02 | 24,751 | 24,729 | `9afb0aaf656ca995632e464815f615c9e3da215a49c8d8bdcfc7bfc51532f397` | `a901db15a560f032c809e92e4ea3af1f128b9edb4fe722d1bc89ee032745fc05` | MISMATCH, proceed under coordinator ruling |

The received bodies have no final newline. A scan outside fenced and inline code found 12
straight apostrophes and 12 straight double quotes in packet 01, and 5 straight
apostrophes and 8 straight double quotes in packet 02. These counts, the 40-byte and
22-byte deficits, and the coordinator's relay test identify lossy typographic-quote
normalization as the cause. The retained bytes are content-identical but not byte-identical
to the original attachments.

The required LaTeX blocks, numbers, digests, SHAs, selectors, instructions, gates, and
prohibitions are present and internally consistent with the canonical sources checked in
this record. No difference beyond prose quote characters was found. The expected packet
digests are recorded as expected values, never as verified values.

The author can restore byte-exact packet identity by pasting the original packets directly
into this pane. That was not done in this execution.
