# Comparison of the two implementations

The registered `describe()` of `bench/logsignals/analyze.py` against the blind implementation's `expected/*.json`. Integers and booleans must be equal, floats must agree within 1e-9, null must meet null.

Data sets: planted, none, edge, edge_ten, edge_eleven, edge_few9. Halves: confirmation, discovery.
Leaf values compared: **660**.
Differences: **0**.

## The registered function on the files as the blind agent wrote them

| set / half | result of `describe()` |
|---|---|
| `edge/confirmation` | `TableInvalid` |
| `edge/discovery` | `TableInvalid` |
| `edge_eleven/confirmation` | `TableInvalid` |
| `edge_eleven/discovery` | `TableInvalid` |
| `edge_few9/confirmation` | `TableInvalid` |
| `edge_few9/discovery` | `TableInvalid` |
| `edge_ten/confirmation` | `TableInvalid` |
| `edge_ten/discovery` | `TableInvalid` |
| `none/confirmation` | `TableInvalid` |
| `none/discovery` | `TableInvalid` |
| `planted/confirmation` | `TableInvalid` |
| `planted/discovery` | `TableInvalid` |

## Control: the blind implementation on the path-normalised copy

The same comparison rule, blind implementation against its own `expected/*.json`. An empty table here means the path rename moved no number, so the comparison above is a comparison of the statistics and not of the rename.

No difference: 0 of the compared leaves moved.

## Differences, registered against blind

No difference in any compared leaf value.

## The registration's second requirement

Repository-blocked `rho_bar` of the first measure (`no_reasoning_share`), from the registered code's output on the path-normalised copies.

| half | planted | none | planted - none |
|---|---|---|---|
| confirmation | `0.44238139787108854` | `-0.008196049198027617` | `0.4505774470691162` |
| discovery | `0.2991268442413053` | `0.01853025719187874` | `0.2805965870494266` |

Every repository-blocked value of the first measure, both sets, both halves:

| set / half | formed | rho_bar |
|---|---|---|
| `edge/confirmation` | `true` | `0.5045387092663506` |
| `edge/discovery` | `false` | `null` |
| `edge_eleven/confirmation` | `true` | `0.373142680038008` |
| `edge_eleven/discovery` | `false` | `null` |
| `edge_few9/confirmation` | `false` | `null` |
| `edge_few9/discovery` | `false` | `null` |
| `edge_ten/confirmation` | `true` | `0.4944064528596969` |
| `edge_ten/discovery` | `false` | `null` |
| `none/confirmation` | `true` | `-0.008196049198027617` |
| `none/discovery` | `true` | `0.01853025719187874` |
| `planted/confirmation` | `true` | `0.44238139787108854` |
| `planted/discovery` | `true` | `0.2991268442413053` |

## Files read (SHA-256)

| file | SHA-256 |
|---|---|
| `bench/logsignals/analyze.py` | `37aa10908e8497d179a2b7e4ae06d9b0b873bceeefd6ecc43e103dbce67fb268` |
| `blind_impl.py` | `194edc0685b428694133315a9bc0b7d65790dcd0951045e3d63b301b87efa4e6` |
| `expected/edge_confirmation.json` | `f1c417fb9083ad74ddfd3676b0ebfc3f0337d722fa68ebac3abb206ca5e95594` |
| `expected/edge_discovery.json` | `21b6fe7ef8df26f75d1ecbaf6786b417d9da6b617118b9880ceee336e7d36574` |
| `expected/edge_eleven_confirmation.json` | `e948f6ac4cf1948c60c82265fff7bd01900bf4041e14f401245c23e23c5b0c63` |
| `expected/edge_eleven_discovery.json` | `cdf35c3c1824b64c6935e9807a8962506095ed019ef3b483b805d77598bf6885` |
| `expected/edge_few9_confirmation.json` | `d08704c764af9e252ca36401a8dac68cb672262d1b719b8fbcc217657a216e64` |
| `expected/edge_few9_discovery.json` | `2c7d9bcf5b036e67b44ebf2df3ebce6ecf542f86a8e4a6623be95012fc71b1c0` |
| `expected/edge_ten_confirmation.json` | `9ba9951bcee5ce2484ec72ebbb0c7219bb108eb9eb7ac7ed788dc2615e1402f8` |
| `expected/edge_ten_discovery.json` | `60dab288b7295e2bd37ae77b8a97cee2414f8b756810f93bda4741bb79bb99f4` |
| `expected/none_confirmation.json` | `f7efbd2bce25e1959d0ea4f45c15cdcdaf3cf4de3be15cfbadea15feb5d9c6cb` |
| `expected/none_discovery.json` | `697ca60373a2178854d2453b804bf045a8675637408c9534a50ac3962efd36fa` |
| `expected/planted_confirmation.json` | `49675b49dc14639156b23c37f92791b1ce3dd9bf6bf6e747bb33a5731a4fe812` |
| `expected/planted_discovery.json` | `48031177e8a5dc31cf5a7d9b12d4f816a3b0d72f3fe2a2996b0e16e952680f77` |

| data set file | as the blind agent wrote it | path-normalised copy |
|---|---|---|
| `sets/planted/signal.tsv` | `3a73a2c38464d1a6bffd700c5b4043fbcf919017edc4663d75a30b4ccdda16bc` | `10d31f86ad6bc8af85e1bc7ed929a791d6d8ab270d29051e6f08fc8994aec510` |
| `sets/planted/outcome.tsv` | `53823b2543f629be06df3fdb334c042cc71b3b198715e5fa3ae6ce1213a37074` | `efba98a233076b142784532e56f09d9fe25beff03dc394f017063265de8356c4` |
| `sets/none/signal.tsv` | `3a73a2c38464d1a6bffd700c5b4043fbcf919017edc4663d75a30b4ccdda16bc` | `10d31f86ad6bc8af85e1bc7ed929a791d6d8ab270d29051e6f08fc8994aec510` |
| `sets/none/outcome.tsv` | `c7f24ccbe8157085e2d3bb5e2a87a07b643b5d236835ea0e3d0d89fcba6fe4aa` | `b04ac90141aa0fd818e7a398b61afbe0d437bf50569bc5297dff592ea8392957` |
| `sets/edge/signal.tsv` | `7cd9f371f121c5c969637e81ed0526e10097316a9995d8983c257bd11e0a664a` | `7cdbba1d548f85034581a1fe6ed38c41bb3402cd4d61bec3743f04c6194ef7e0` |
| `sets/edge/outcome.tsv` | `5efd040ed39941334b6e10da7c5df9bf56e76db721f18c87c5e081b37ee3132f` | `adf0b415b301707431e43cce03b78c8f6aabdca57956ab0659531c34566683ef` |
| `sets/edge_ten/signal.tsv` | `5710df85292e22756535361861136e54b27009fa7f5a7a55f7632a4472a6fdce` | `bf66792ecc2e74d9b8e5ee10d58601fcc23b91348d8d30c5989c9b33c2951d46` |
| `sets/edge_ten/outcome.tsv` | `d3e8a9a4a1518b7c8b09ba2fcc374f1236baf04cb1d579c944891cc544d73283` | `0f003d3791be1054c949d856937a975067a9d4d091131e3edffb8b7ccea7ce44` |
| `sets/edge_eleven/signal.tsv` | `2e2f6680e8db712c1ccd2898c4046d060a7b703eb805de22af8f554a686f572d` | `b93e2ae7d78bdd02cec13fdd2e18c5a1cc7ce85cfb451b71e04748d24ae8985b` |
| `sets/edge_eleven/outcome.tsv` | `625322b2a41fe389b9af12a9027380875a344e2e24b69be20cb757a522a7953f` | `6959329dc7531a49462f7ea4e0141895797fdd5b1b4a5b2ce77aacda025035d5` |
| `sets/edge_few9/signal.tsv` | `838f91c137c0eaa65b7d678c0005ff8a44d805e2e16540742efe6a838717af18` | `3c295a9697a61e4d423d1d74dc1ae9db029c8d7f79bef0d9ba60749fde807227` |
| `sets/edge_few9/outcome.tsv` | `7925290920ccc5b5f2841fbd4839c2640ac9b9b34e1cc4840707220d58268256` | `0ff421d3b0f19726375bfd410c5369325439dc8406ff1bba13cfe6fd00be6e8e` |

