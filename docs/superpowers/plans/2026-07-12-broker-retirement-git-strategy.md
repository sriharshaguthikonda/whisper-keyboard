# Broker Retirement — Git Strategy

Status: DRAFT (planning). Final path chosen by Q3 in `Q and A.md` (2026-07-12).
Pairs with `docs/superpowers/specs/2026-07-12-input-owner-simplification-design.md`.

## Lineage facts

- Pre-broker base: `03edf96 feat: use left ctrl chord-safe dictation trigger`.
- First broker commits: `d4bd371` (plan), `2061e46 feat: add Python broker
  command dispatcher`, `edeb325 feat: scaffold Rust hotkey broker state machine`.
- Current branch under review: `feature/ask-ai-voice` at `740ea1f`.
- Remote: `github.com/sriharshaguthikonda/whisper-keyboard` (origin + new-origin).
- Working tree is DIRTY (Ask-AI WIP: `ask_ai_bridge.py`, `commands_and_tools.py`,
  `settings_manager.py`, `transcription_config.json`, `Settings_GUI.py`,
  `Start-WKeyBroker.ps1`, tests). Commit or stash before any history operation.

## Why history is entangled

Since `03edf96`, ~50 commits landed. Classifying by whether they touch the
broker core (`native/` or `wkey/broker_control.py`):

- pure-broker ≈ 4 (e.g. `edeb325`, `102aefe`, `26a44e8`, `f713476`)
- mixed (broker core + shared files) ≈ 6 (e.g. `2061e46`, `475356c`,
  `5648ff5`, `fbae33f`, `ee476ff`, `e5ba67d`)
- everything else ≈ 40, INCLUDING broker *wiring* that lives in shared files
  not counted above: launcher scripts (`Start-WKeyBroker.*`,
  `Install-WKeyBrokerTask.ps1`) and broker-mode branches inside
  `wkey/faster_whisper_Mother_of_all_wkey.py`. So true broker entanglement is
  wider than the 10 core-touching commits.

Non-broker features (Control Center `55b9a74`, speaker filter `6a39705…d00622f`,
Ask-AI `aa12ba6…740ea1f`, audio fixes `9521dc5`, `37d87da`) are interleaved with
broker commits, and Control-Center/activation code references broker mode. A
clean split is not a straight `git rebase --onto`.

## Retirement surface (current tree)

- `native/wkey-broker/` — delete (or, option B, reduce to input-only bridge).
- `wkey/broker_control.py` — delete.
- `wkey/faster_whisper_Mother_of_all_wkey.py` — 30 refs behind
  `WKEY_INPUT_OWNER=broker` / `run_control_stdio`; default owner → python,
  remove broker branches.
- `wkey/control_center.py` — 1 broker status ref; un-wire/relabel.
- `scripts/Start-WKeyBroker.ps1`, `Start-WKeyBroker.bat`,
  `scripts/Install-WKeyBrokerTask.ps1` — delete or repoint to direct Python
  launcher + logon-only task.

## Path 1 — Abandon-in-place (RECOMMENDED)

Keep all history. Do a normal forward change on a new branch off
`feature/ask-ai-voice`.

1. Commit/stash the dirty Ask-AI WIP first.
2. `git switch -c chore/retire-broker feature/ask-ai-voice`.
3. Per the phased spec: fix scheduler/launcher, default input-owner → python,
   remove broker-mode branches, delete `broker_control.py` + `native/` (option
   A) or reduce `native/` to the input-only bridge (option B), delete/repoint
   launcher scripts, remove/repurpose broker tests.
4. Small commits per phase; run tests + `git diff --check` + bounded smoke each.

Pros: zero cherry-pick risk, same functional end state, trivial to review.
Cons: history still shows the broker was built and removed (no functional cost).

## Path 2 — Clean-history rewind (only if Q3 explicitly wants broker-free history)

1. Commit/stash WIP.
2. `git switch -c refactor/no-broker 03edf96`.
3. `git cherry-pick` only the non-broker commits, in order: Control Center,
   speaker filter (`6a39705`, `300bb91`, `3c91611`, `8232efe`, `d00622f`),
   audio fixes (`9521dc5`, `37d87da`, `95567b0`), Ask-AI (`aa12ba6`, `aa0e9d4`,
   `d677074`, `740ea1f`), plus any doc/settings commits worth keeping.
4. Expect conflicts wherever a kept commit touched broker-mode code paths
   (Control Center status, activation stream ownership). Resolve by taking the
   non-broker intent and dropping broker branches.
5. Re-run the full test suite; the end state must match Path 1.

Pros: history looks as if the broker never existed.
Cons: high effort, real conflict risk from interleaving, easy to silently drop a
non-broker fix. No functional advantage over Path 1.

Recommendation: Path 1 unless a broker-free history is explicitly required.

## Verification (either path)

- Full Python suite passes; broker-specific tests removed or repurposed.
- `native/wkey-broker` gone (A) or input-only (B); no `wkey-broker.exe` in
  startup.
- Sleep→wake keeps dictation alive with no kill/restart; on-battery does not
  stop the app; stale `pid=unknown` lock is reclaimed.
- Bounded primary-script smoke: starts, survives 20s, stops by PID, no leftover
  process.
