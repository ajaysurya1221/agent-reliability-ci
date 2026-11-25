# Reply-0, day 1: the environment (Task A, servers and probe)

Written 25 November 2026. Design evidence only: **no model was called**, no Ollama, no model API.
Everything below was installed and run on one laptop (macOS 27.2.1, build 26B131, arm64).

Paths. `$ENV` is the pinned environment directory, outside the repository on the laptop that
runs the study; `$ARCI` is the repository; `$HOME_DIR` is the account's home folder. The three
names stand in for the real paths in every file published under `reply-0/`, so no published
file carries a personal folder name. The scripts take `$ENV` as their first argument or from
`REPLY0_ENV`, and `probe.py --redact PATH=NAME` writes the names into its own output.

`$ENV` holds:

| Path | What it is |
|---|---|
| `py/` | Python 3.13.12 virtual environment: released ARCI 2.4.1 and the reference git server |
| `node/` | `package.json`, `package-lock.json`, `node_modules/`: the reference filesystem server |
| `home/` | an empty directory given to every server as `HOME`, so no personal configuration is read |
| `orderdesk-state/` | where the ARCI bridge writes its `state.json` |
| `pip-report.json`, `requirements.freeze.txt` | what pip installed, with the hash of every wheel |

The fixture is **not** under `$ENV` any more: it is `/Users/Shared/arci-reply0/fx` (`$FX`), the
registered path of the benchmark. See "The fixture" below.

One exception, on purpose: `boundary-check/` (task C of the same day) still holds the real paths
in 130 files. Its `runs/` and `runs-repeat/` are sealed ARCI stores, and the sha256 of each
`manifests/*.yaml` is recorded inside them, so rewriting any of it would break the seal or make
the record disagree with itself. It is left exactly as it was run, and nothing under it is part
of the digest list the registration pins. Whoever publishes the benchmark decides separately
whether that folder goes out.

(`checkers/` in the same directory belongs to another task of the same day, not to this one.)

## Tools already on the machine

| Tool | Version | Path |
|---|---|---|
| Python (base interpreter of the venv) | 3.13.12 (Clang 22.1.1) | `$HOME_DIR/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/bin/python3.13`, the interpreter behind `run4-env/bin/python` |
| pip (inside the venv) | 25.3 | `py/bin/python -m pip` |
| Node.js | v24.18.0 | `$ENV/node/bin/node`, SHA-256 `ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a` |
| npm | 11.16.0 | package installation tool |
| git | 2.55.0 | `/opt/homebrew/bin/git`, first on the PATH the servers are given |
| git (also installed, not used) | 2.54.0 (Apple) | `/usr/bin/git` |
| `python3` that ran `fixture.py` and `probe.py` | 3.14.6 (standard library only) | `$HOME_DIR/.local/share/mise/installs/python/3.14.6/bin/python3` |

## The three servers

| Server | Package | Version | Released | Says about itself at `initialize` | Protocol answered |
|---|---|---|---|---|---|
| filesystem | `@modelcontextprotocol/server-filesystem` (npm) | **2.4.0** | 18 Nov 2026 | `{"name": "secure-filesystem-server", "version": "2.4.0"}` | `2025-11-25` |
| git | `mcp-server-git` (PyPI) | **2026.11.18** | latest on PyPI on 25 Nov 2026 | `{"name": "mcp-git", "version": "2026.11.18"}` | `2025-11-25` |
| order desk | `agent-reliability-ci` (PyPI), module `arci.mcp_toolset_server`, serving `orderdesk/orderdesk_world.py` | **2.4.1** | | `{"name": "arci-toolset", "version": "0.2"}` | `2026-07-28` |

The probe asks every server for protocol version `2025-11-25`. The two reference servers answer with
it. The ARCI bridge always answers `2026-07-28`, whatever is asked.

Both reference servers were on the `latest` tag of their registry on 25 November 2026. The
filesystem server changed its version numbering in October 2026 (from dates such as `2026.8.31` to
`1.0.0`, `2.0.0` ... `2.4.0`); `2.4.0` is the newest by date, and the registry lists a build
provenance attestation for it.

## Python: exact commands

```sh
mkdir -p $ENV
cd $ENV
export PYTHONDONTWRITEBYTECODE=1
$HOME_DIR/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/bin/python3.13 -m venv py
py/bin/python -m pip index versions mcp-server-git        # newest: 2026.11.18
py/bin/python -m pip install --only-binary=:all: --no-compile --report pip-report.json \
    "agent-reliability-ci==2.4.1" "mcp-server-git==2026.11.18"
py/bin/python -m pip freeze > requirements.freeze.txt
```

`--only-binary=:all:` means only wheels were installed, so no package's build script ran. `uv` was
not used. 34 packages were installed; pip 25.3 itself came with the venv.

- `pip-report.json` sha256 `b96638d8c3744d3e55241e1ac9d28322a9205f6b63d7c555e069d94930001699`
- `requirements.freeze.txt` sha256 `3e0a323b5871b96b99abc490f3a7bf20c58eaccb86c2297991997b009b03ef84`

| Package | Version | Wheel | sha256 of the wheel (from pip's report) |
|---|---|---|---|
| `agent-reliability-ci` | 2.4.1 | `agent_reliability_ci-2.4.1-py3-none-any.whl` | `9e3e41e43959ece5b0ad11c6f3754674d97275bd499fc643d45ef89202e31ca7` |
| `annotated-types` | 0.8.0 | `annotated_types-0.8.0-py3-none-any.whl` | `f072f4d804ea359e4eaf198b1af7a8b0943881a87f31bb764f8bf219bb9419e0` |
| `anyio` | 4.16.0 | `anyio-4.16.0-py3-none-any.whl` | `c66ae634e0b8228396b801741beb3294326d4b6102f7bba4041c0dfb58c29026` |
| `attrs` | 26.1.0 | `attrs-26.1.0-py3-none-any.whl` | `c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309` |
| `cffi` | 2.1.1 | `cffi-2.1.1-cp313-cp313-macosx_11_0_arm64.whl` | `19ee6127ee34de7d83ce3d371ebc5ed91addbdcc39f9ab15ce4eb35a4e534971` |
| `click` | 8.5.1 | `click-8.5.1-py3-none-any.whl` | `8bb5376d2006950386f8c6427613334a2acadc5f559cb80e638d00b4df957e37` |
| `cryptography` | 50.0.2 | `cryptography-50.0.2-cp311-abi3-macosx_11_0_arm64.whl` | `fa8f5efb344d6908a1ce62f4a24e2e5780f825d6f53f5f50ec5ffacac72936cb` |
| `gitdb` | 4.0.12 | `gitdb-4.0.12-py3-none-any.whl` | `67073e15955400952c6565cc3e707c554a4eea2e428946f7a4c162fab9bd9bcf` |
| `GitPython` | 3.2.1 | `gitpython-3.2.1-py3-none-any.whl` | `d66b0832aa8755c1a84892937282df0befb16c97e5a64aeebd68be9c5e323f53` |
| `h11` | 0.16.0 | `h11-0.16.0-py3-none-any.whl` | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` |
| `httpcore2` | 2.16.2 | `httpcore2-2.16.2-py3-none-any.whl` | `16051ae2a42f776007543f32de9349a317b23d2cbb4e1456b4bac0e88b87419a` |
| `httpx2` | 2.16.2 | `httpx2-2.16.2-py3-none-any.whl` | `f05c13aade4c45dbf1c9060647a1058f0acad62398fad96e741269edb33d46f5` |
| `idna` | 3.20 | `idna-3.20-py3-none-any.whl` | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` |
| `jsonschema` | 4.26.0 | `jsonschema-4.26.0-py3-none-any.whl` | `d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce` |
| `jsonschema-specifications` | 2025.9.1 | `jsonschema_specifications-2025.9.1-py3-none-any.whl` | `98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe` |
| `mcp` | 2.3.0 | `mcp-2.3.0-py3-none-any.whl` | `dd0c44c089d16453e8ae31a3877a0054d7a2314caaa81f5e0541b9b1734b2377` |
| `mcp-server-git` | 2026.11.18 | `mcp_server_git-2026.11.18-py3-none-any.whl` | `4a1b5ee4edbc657eddec4b3ba809e458b50a03150f0295c3eaad426c8a19ffc2` |
| `mcp-types` | 2.3.0 | `mcp_types-2.3.0-py3-none-any.whl` | `968efdbdaedfab06adae40d378a34395f1090c5921d4be3c9cde283aaf76d91d` |
| `opentelemetry-api` | 1.45.2 | `opentelemetry_api-1.45.2-py3-none-any.whl` | `2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34` |
| `pycparser` | 3.12 | `pycparser-3.12-py3-none-any.whl` | `a076f3f489b39b43ed13563a1dafe42447445bec2e294154ec5c57fcdda4c85e` |
| `pydantic` | 2.14.4 | `pydantic-2.14.4-py3-none-any.whl` | `653a2ad9f6d8858529c77c72717d0ea991d6c6837fe683246b2f4b2bbfc3fadc` |
| `pydantic_core` | 2.50.5 | `pydantic_core-2.50.5-cp313-cp313-macosx_11_0_arm64.whl` | `639a51931869c0594d8723b2f529c547db1aa33dc9571d001dc205d896170c08` |
| `PyJWT` | 2.15.1 | `pyjwt-2.15.1-py3-none-any.whl` | `42d59d631f7768a1028a64c7ff581a9bf7519804daf91fc5b6c56e30eec5e193` |
| `python-multipart` | 0.0.34 | `python_multipart-0.0.34-py3-none-any.whl` | `ebacd224bd686eee2f9aa1066a657affe07435a185834e05e5235e2e59173e91` |
| `PyYAML` | 6.0.4 | `pyyaml-6.0.4-cp313-cp313-macosx_11_0_arm64.whl` | `9d4211f080920629a90c9e31c51e326fb70cfae38f18d4128b9913c23642bace` |
| `referencing` | 0.37.0 | `referencing-0.37.0-py3-none-any.whl` | `381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231` |
| `rpds-py` | 2026.9.1 | `rpds_py-2026.9.1-cp313-cp313-macosx_11_0_arm64.whl` | `eba5d173f7d5708b22a93815017a4611873ed54db9f268077c0dd1ed99cfc858` |
| `smmap` | 5.0.3 | `smmap-5.0.3-py3-none-any.whl` | `c106e05d5a61449cf6ba9a1e650227ecfb141590d2a98412103ff35d89fc7b2f` |
| `sse-starlette` | 3.7.1 | `sse_starlette-3.7.1-py3-none-any.whl` | `c1bb3af0508c6c24cd4ab6257047654bbec01456a424bed36b36e8020cd7a37f` |
| `starlette` | 1.10.0 | `starlette-1.10.0-py3-none-any.whl` | `478c0ab3b4ced6e82719849c118fa406f0278a3499c1a898cd15cd31bdc38ce4` |
| `truststore` | 0.10.5 | `truststore-0.10.5-py3-none-any.whl` | `9aaaedaefaf06d8b206278cf8b5012bc897f485a874503501e12d776df78951c` |
| `typing-inspection` | 0.4.5 | `typing_inspection-0.4.5-py3-none-any.whl` | `bc210535442b39e1bf2805e0c7a17dfd6a4ace760c84c7f7d16245d23a6b1c39` |
| `typing_extensions` | 4.16.0 | `typing_extensions-4.16.0-py3-none-any.whl` | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |
| `uvicorn` | 0.54.0 | `uvicorn-0.54.0-py3-none-any.whl` | `505bdb0f318731d45f1f712071fc781a8981f6847a31c902c9f5e652d4f67faf` |

`agent-reliability-ci` 2.4.1 pulls in only `pydantic` and `pyyaml` (and what they need); the rest
comes with `mcp-server-git` (`mcp` 2.3.0, `GitPython` 3.2.1, `click`, and what they need).
LangChain is **not** installed, on purpose: it is not one of the pinned packages of this task.

## Node: exact commands

```sh
mkdir -p $ENV/node
cd $ENV/node
printf '{\n  "name": "reply0-env-node",\n  "version": "0.0.0",\n  "private": true\n}\n' > package.json
npm view @modelcontextprotocol/server-filesystem version dist.integrity      # 2.4.0
npm install --ignore-scripts --save-exact --no-audit --no-fund \
    @modelcontextprotocol/server-filesystem@2.4.0
```

`--ignore-scripts`: no install script of any package ran (the lockfile marks none as having one).
`package.json` now pins `"@modelcontextprotocol/server-filesystem": "2.4.0"`.

- Lockfile integrity of the server: `sha512-BoT8Gws5MsetfAey4vDyuzy8WYQES6mGYLSShuqSNGAC0X0NBV4p78/R78KfW4RkxtWz+zxhS9jwhzJrQUTt2Q==`
  (the registry's `dist.integrity` for 2.4.0 is the same string; registry shasum `172f7d8fcd0d85205db041291a47f05bb2042d92`)
- `package-lock.json` (lockfileVersion 3) sha256 `eed9ef81e41d799c76243af77bf6c1d97a013058ad95cd1008aa040fe52bd1a1`
- `package.json` sha256 `ee9bc9ca0e49e767608af972d40a8c5e264e52ccfebae1f1c7ebead16d98ed30`

| Package (12 in all) | Version | Lockfile integrity |
|---|---|---|
| `@hono/node-server` | 2.1.11 | `sha512-KzKz9vl4vvr1vgLHamj+g5uonbrj5NwAdO3yzOS6cd2HjALVeOgTgeZOyAzNxejbkfOOPIcvuf/Tg8l1pEFLog==` |
| `@isaacs/nonrecursive-glob-match` | 1.1.0 | `sha512-GPm/Dbvk5RLmhRnxXIa7nTpK0xtl4E0wj0MslsuNiJ1FIROU+2+9lgUC/dgF7Ey4QCWhfEsgxilMRMCdHPfDfw==` |
| `@modelcontextprotocol/core` | 2.4.0 | `sha512-z8QBKqdfXLPzkLQuG4xp8hrVEMm1PZ1IgxMN2sMbJiFiAKOWXnAzogXn2W4aqIBlP1ea6U5yiqVquvUNM1Cj6Q==` |
| `@modelcontextprotocol/node` | 2.1.2 | `sha512-IIcIqBpr6NCQQs5DgJTgvbSOAw+3iaR/uquqg+e0nXCdudfjPg/80x0TseUnQx14AUAtE4fsJCEpJKPyb6WPVA==` |
| `@modelcontextprotocol/server` | 2.4.0 | `sha512-rgR9yxSaAJ+bcsi/XroT/S2AfPiIWloXAnrdfYSCms9ivVju0ishu/wW0J21Ho6+ZOR1r7RyeRbjiRuF87ix5Q==` |
| `@modelcontextprotocol/server-filesystem` | 2.4.0 | `sha512-BoT8Gws5MsetfAey4vDyuzy8WYQES6mGYLSShuqSNGAC0X0NBV4p78/R78KfW4RkxtWz+zxhS9jwhzJrQUTt2Q==` |
| `balanced-match` | 4.0.4 | `sha512-BLrgEcRTwX2o6gGxGOCNyMvGSp35YofuYzw9h1IMTRmKqttAZZVU67bdb9Pr2vUHA8+j3i2tJfjO6C6+4myGTA==` |
| `brace-expansion` | 5.1.0 | `sha512-aa11Dv491GKnYqxaul3aRJ0szew7yMJMfZPnqD44NjGrZXoj62l41OEDDpdpC4eE2P88vBFfLuSyRhpG91NUvg==` |
| `diff` | 8.0.4 | `sha512-DPi0FmjiSU5EvQV0++GFDOJ9ASQUVFh5kD+OzOnYdi7n3Wpm9hWWGfB/O2blfHcMVTL5WkQXSnRiK9makhrcnw==` |
| `hono` | 4.13.22 | `sha512-wncKd5/40Pj8grx0RZ2fgNIicFEmVFwIHT5UFLTnphR8I6AQWFf9c2JoM6ZJ9g8y4pMzg3sNlCVNe0m2Yclg0Q==` |
| `minimatch` | 11.0.9 | `sha512-KCFkfyjqerNlSstjlhIGNXIKZGA/6O4V4RlhZ+Dsr621SPPw0mzlypE9D9ZOoPiVefHID+j7/XuMMlqfD/F60Q==` |
| `zod` | 4.6.7 | `sha512-g8W2D2kU6a8untc053fX1uVBKzM7yqAxW/3zwk83+6RyF2+SKOuV+c0wBDhUwzV1PaGapmZH+rmcUzPf+3CGwg==` |

## The fixture

```sh
python3 -B $ARCI/plan/exec/v2/study/reply-0/fixture.py /Users/Shared/arci-reply0/fx
```

`fixture.py` uses the standard library and the `git` program. It writes twelve text files in two
folders (`files/notes`, `files/data`), a git repository `repo/` with five commits on `main` and a
branch `release-1` at the third commit, and `manifest.json`. It switches off the user's and the
system's git configuration, fixes author, committer and dates, and never deletes anything (it
refuses a directory that is not empty). Built three times in three different places: the three
`manifest.json` files and the three trees were identical.

The registered fixture path is `/Users/Shared/arci-reply0/fx` (`$FX`). It was moved there on
25 November 2026, out of `$ENV/fixture`, so that no ask, reply or published store carries a
personal folder name. `/Users/Shared` is a real directory of macOS, not under `/tmp`, `/var`
or `/etc`, and neither it nor `arci-reply0`, `fx`, `fx/files` or `fx/repo` is a symbolic link
(checked with `os.path.islink` and `os.path.realpath`, which the filesystem server's resolved
paths must agree with). The manifest of the fixture built there is the registered one, so the
move changed no key, no reply and no hash below.

- `manifest.json` sha256 `9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea`
- `fixture.py` sha256 `17fd2e4d7a25b1e451da353b3e5fcb0ef61a2fa51632847b42f9756fe5da29d2`

| Commit | Date | Author | Message |
|---|---|---|---|
| `0b956b19a23106abe9fdf3d48ef021b56dd1b33a` | 2026-01-05T09:00:00+00:00 | Asha Verma | Add the price list |
| `67c5f2e7f980d981b64d1298a0d2f862eba1403d` | 2026-01-06T10:30:00+00:00 | Bram de Wit | Add the total calculator |
| `25018bef76af977432b507d764ac7f5123fa9752` | 2026-01-12T14:15:00+00:00 | Asha Verma | Add brackets and wall plugs to the price list |
| `911021e1ef1ae2a50fbf18ce67fb7fdd84aadce2` | 2026-02-02T08:45:00+00:00 | Bram de Wit | Round totals to whole cents |
| `220e18235909e69ffa83b5ad59d3a05739598c15` | 2026-03-01T07:00:00+00:00 | Asha Verma | Raise the oak shelf to 135 |

Branches: `main` -> `220e18235909e69ffa83b5ad59d3a05739598c15`, `release-1` -> `25018bef76af977432b507d764ac7f5123fa9752`.
Tracked files in `repo/`: `CHANGELOG.md`, `README.md`, `prices.csv`, `total.py`.

| File | sha256 of its content |
|---|---|
| `files/data/config.json` | `ffdd4131b6869071c4184931d974730c3ed4d7c40d4fefc4cdb4bb1c56e282df` |
| `files/data/orders.csv` | `6b5972ccc163da70d63336d3c7a56ea36e2f80ce0e034eab728c18c13865c79c` |
| `files/data/prices.csv` | `2212a6e298b09f1e0ffabbd34a74c1b498b2baffc9a121be21fe9ffbfc2e96a9` |
| `files/data/returns.txt` | `ac0eb48479acf522bc6987e019d2699fe1582ad0c6ccd4162cf29b32fcf68893` |
| `files/data/stock.csv` | `0ee9f21f60460247d6477f5c071bc2f82d9e5855e4d293df763497bd0e87d18e` |
| `files/data/suppliers.txt` | `b166fa8084c34cabafab31c865c3927c2708138b02495d50e29e3d93a4a9a7f9` |
| `files/notes/contacts.txt` | `4a2941ba4b7b85a96f7d0c41d18b42e917dfb57c7775a7eef772e541c4385fc1` |
| `files/notes/glossary.md` | `2a62b8286b739ee8c89a7079b1db82f91eef59b933a202f47c42817eaf67d46d` |
| `files/notes/meeting-2026-01-05.txt` | `ae4a86ea2d9cb888e5828c9fe8d55cce136bb8456a4da2f1a7ba21e0bf6595b5` |
| `files/notes/meeting-2026-01-12.txt` | `c0c68a74baf513e6217f4861d8cf2304d702138137f681ec7e694bbe0dd6cbea` |
| `files/notes/readme.md` | `808497660e52daed61a5d6a96e15f70a71bff8d279836bc8bce5f86a4ef0de9a` |
| `files/notes/todo.txt` | `748c6d47f04e788ff2ac53c3526bcfa1e394fbefb633f9580f75570dfbd6f38d` |

File modification times are set to 5 January 2026 09:00 UTC. Creation times and inode numbers are
the operating system's and differ from build to build (the filesystem server's `get_file_info`
shows them).

## The probe

```sh
sh $ARCI/plan/exec/v2/study/reply-0/run_probe.sh $ENV /Users/Shared/arci-reply0/fx
```

It builds the fixture if it is missing, then probes the three servers. The second argument
defaults to the registered fixture path; the first must be given, or `REPLY0_ENV` set.

`run_probe.sh` holds the three exact command lines. In short, each server is started as

```sh
# filesystem
sandbox-exec -p '(version 1)(allow default)(deny network*)' \
    "$ENV/node/bin/node" $ENV/node/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js /Users/Shared/arci-reply0/fx/files
# git
sandbox-exec -p '(version 1)(allow default)(deny network*)' \
    $ENV/py/bin/python -m mcp_server_git --repository /Users/Shared/arci-reply0/fx/repo
# order desk (PYTHONPATH=$ARCI/plan/exec/v2/study/reply-0/orderdesk)
sandbox-exec -p '(version 1)(allow default)(deny network*)' \
    $ENV/py/bin/python -P -m arci.mcp_toolset_server --toolset orderdesk_world:make_tools \
    --workdir $ENV/orderdesk-state --seed 0 --task-file $ARCI/plan/exec/v2/study/reply-0/orderdesk/task.json
```

- All three run with the network denied by `sandbox-exec`. None of them needs it.
- The probe gives each server a small fixed environment: `PATH`, `HOME=$ENV/home` (empty),
  `LC_ALL=C`, `TZ=UTC`; the git server also gets `GIT_CONFIG_GLOBAL=/dev/null` and
  `GIT_CONFIG_NOSYSTEM=1`; the Python servers get `PYTHONDONTWRITEBYTECODE=1`. The first line of
  each `probe/<server>.jsonl` records the command, the environment, the redactions and the
  sha256 of the plan and of `probe.py`.
- Everything the probe writes goes through `--redact`: `$ENV`, `$ARCI` and `$HOME_DIR` replace
  those absolute paths in `probe/<server>.{jsonl,md,stderr.txt}`, longest path first. Only the
  written files change; the servers were sent the real paths.
- The filesystem server runs in its default mode (not `--read-only`), so `tools/list` shows its
  write tools and their annotations. The probe calls only tools whose `readOnlyHint` is true.
- The git server is confined to the fixture repository with `--repository`.
- The probe declares no client capabilities (no Roots), so the filesystem server keeps the
  directory from its command line.

| File | sha256 |
|---|---|
| `probe.py` | `80f09bbadf2f9bb7dc4de1c89cab7fd342842561e883672ff6a0e84d7d777e69` |
| `run_probe.sh` | `f45b2c04a5d9ea816826d326ff16332eebc75f17d350a56627c3e3def58ada69` |
| `tasks/tasks.json` | `c8fa766907fad3a5db50a2af8654504c00a1d3312ee21e8c771fb4219d140d36` |
| `tasks/make_tasks.py` | `5a76b2caf347ad97393bf1b6da60f1cc40dbbef3e9034fe358bde7ce0f03b625` |
| `tasks/check_tasks.py` | `351d494b26a44eb490cce7f5f521869245b880cd2a9990c46ea945077235f74b` |
| `plans/filesystem.json` | `0134f62450d53397495e8dd67cf70c2cade53717fd4b5d21ecd41ddab92979bc` |
| `plans/git.json` | `ee4240b7eb283f31464b98cbddee3cd4c62febcfbff262c9d7cec717aaff1b9a` |
| `plans/orderdesk.json` | `60f7989ef78fd291d1ec142495d3c98763891ff3b1c4856b08cacb046a3248bb` |
| `orderdesk/orderdesk_world.py` | `a57b31b100361eaee45bb135c6c57cf6123f739d878b58cfc580acc36f5dadfa` |
| `orderdesk/task.json` | `1d6b1e4ef555cc1f8d617c4a7d4e5656ac90224ae1f2332fe3b09c82520b61b4` |

The files under `probe/` carry the fixture path and a start time, so they are not the same from
machine to machine. Two runs one after the other on 25 November were compared record by record:
apart from the first line of each `.jsonl` (the start time), every request and every reply was
identical on all three servers (75, 62 and 19 lines). The probe was run once more the same day,
after the fixture moved to `$FX`, with the redactions in place: 66 bad calls on the three
servers again (32, 28, 6), 39 of their replies holding the name of the wrong argument.

## The order desk as an MCP server: what exists and what does not

- A stdio MCP bridge exists in released ARCI: `python -m arci.mcp_toolset_server --toolset
  MODULE:FACTORY --workdir DIR --seed N [--task-file FILE]` (`src/arci/mcp_toolset_server.py`, also
  on `origin/main`; used by `examples/recipes/mcp_agent`).
- **No stdio order-desk server exists.** The order desk (`plan/exec/v2/study/order-desk*/tools.py`,
  the same file in all six folders) returns LangChain `StructuredTool` objects inside `ToolEnv`.
  The bridge wants an object with a `tools` mapping of plain functions and a `snapshot()` method,
  and LangChain is not in this environment.
- For the probe, `orderdesk/orderdesk_world.py` is that same `make_tools` with the last statement
  changed to return the plain functions (the body up to the `return` is identical, checked by a
  string comparison). It is study code and nothing under `src/` uses it.
- Limits of that stand-in: the bridge sends **no annotations**, so the server itself never says
  which tools are read-only (the plan names `lookup_order` and `check_stock`); the bridge does not
  check arguments against the schema, so a missing argument comes back as Python's own
  `TypeError` text, and a number in place of a string reaches the tool unchanged; the bridge's
  diagnostic formatter turns the digit in that `TypeError` into `<n>`. In runs 2 to 6 the model's
  calls went through LangChain's argument check instead, so only the two replies "unknown order"
  and "unknown SKU" are the order desk's own words in both settings.
- The control of D-33 (a raw empty result against the naming sentence) is a fault ARCI injects at
  its boundary. The order desk never returns an empty result by itself, and the probe did not
  provoke one.
