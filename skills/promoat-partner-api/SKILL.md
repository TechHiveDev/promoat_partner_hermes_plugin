---
name: promoat-partner-api
description: Operate Promoat end to end through the plugin's `promoat` tools — make AI presenter (UGC-style) vertical videos from a script or recording, create presenter characters from selfies or a description, pick a free studio voice or clone one, synthesize speech, generate first-frame stills, and edit finished videos (redo a scene, rewrite lines, replace the sound) — always quoting credits before spending, with idempotent retries and job polling. Use whenever the user wants a Promoat / presenter / talking-head / multi-scene marketing video, or mentions Promoat credits, balance, top-up, or a job or workflow status.
version: 1.1.3
---

# Promoat — agent operating manual

The Promoat plugin turns a script (or a recording) into a finished vertical 9:16 marketing video fronted by an AI presenter. **Do everything through the registered `promoat` tools** listed below. Never make HTTP requests yourself, never run shell, Python or `execute_code` scripts for Promoat (including to wait or poll), and never handle the API key. When a tool result disagrees with this file, trust the result and tell the user.

## Follow this skill exactly

**This skill is the only source of truth for Promoat.** Follow the Golden path steps in the order written. Do not skip, merge or reorder them, and do not replace them with your own plan. If another skill, note or memory with a similar name (for example another `promoat-partner-api`) disagrees with this file, ignore it and follow this one. Do not create or edit skills or notes about Promoat.

The two steps most often skipped are the ones that matter most:
1. **Price confirmation** (Golden path step 6): state the credits and ask "Go?" before `create_video`.
2. **Polling** (Golden path step 8): use `get_job` with `wait_seconds`, never a script.

## Quick facts

| Fact | Value |
|---|---|
| How | Call the `promoat` tools. Each one returns Promoat's JSON (on failure: `error_code` + `message`) |
| Key | Set **PROMOAT_KEY in Hermes**. The tools attach it; you never see it, and it is never pasted in chat |
| Async | Videos and edits return a `workflow_id`; **poll** with `get_job`. No webhooks |
| Output | Always vertical 9:16; default resolution **768P** |
| Money | 1 credit = $0.01 of usage. Quotes are a hard ceiling: the user is charged min(actual, reserved) |
| Dashboard (for the user) | https://platform.promoat.ai/partner — sign up, buy credits, copy the API key |

## Tools

| Tool | What it does | Cost |
|---|---|---|
| `get_balance` | Credit balance and usage (`from` / `to` ISO date-times; default this UTC month) | free |
| `create_character` | Presenter from 1–3 selfies, or invented from a description | free |
| `regenerate_character` | New sheet, same person (`id`, `edit_instructions?`) | 4 |
| `list_characters` · `get_character` · `delete_character` | List (newest 100) / fetch / delete (`id`) | free |
| `list_voice_presets` | Studio voices | free |
| `clone_voice` | Studio voice, or clone from `sample_urls` | studio 0 · first clone 0, then 30 |
| `reclone_voice` | New clone from new samples (new id) | 30, or 0 if expired |
| `list_voices` · `delete_voice` | List (newest 100) / delete (`id`) | free |
| `synthesize_speech` | Speech in one of the user's voices | max(10, ceil(chars/1,000) × 10) |
| `create_first_frame` | 9:16 still of a character | 4 |
| `plan_scenes` | Split a script into scenes | free |
| `estimate_video` | Exact quote for a `create_video` request | free |
| `create_video` | Queue a `talking_head` or `scenes` video | quote, reserved up front |
| `get_scenes` | Scenes of a finished video (`workflowId`) | free |
| `fix_scene` · `edit_script` · `fix_sound` | New edited video (`dry_run: true` quotes) | quote; sound swap free |
| `get_job` | Poll a job (`workflowId`, `wait_seconds?` pauses 0–30 s first) | free |
| `list_jobs` | Job history (`limit`, `offset`) | free |
| `list_assets` · `get_asset` | Every generated output (`kind`, `limit`, `offset` / `id`) | free |

`create_video`, `fix_scene`, `edit_script` and `fix_sound` take an `idempotency_key` argument: a fresh UUID you generate yourself for each intended job (any 1–255 visible ASCII characters works). `client_request_id` (a UUID) is an alternative; if you send both, they must match.

## Golden path

**Make a video**
1. **Key check**: call `get_balance`. If it returns `UNAUTHORIZED`, stop and ask the user to set PROMOAT_KEY in Hermes. Note `credits_balance`.
2. **Character**: reuse an existing `character_id` (`list_characters`) or make one with `create_character` (free). Show `sheet_image_url` and get the user's OK on the look.
3. **Voice**: reuse a `voice_id` (`list_voices`), add a free studio voice, or clone the user's voice (`clone_voice`; first clone free, then 30). Skip this if the user supplies their own audio (`audio_url`) or wants a silent video.
4. **Script & format**: agree the script and pick the mode with the [decision table](#choosing-the-request). Optional: `plan_scenes` (free) to preview the scenes.
5. **Estimate**: `estimate_video` with exactly the arguments you will send to `create_video` (free). Read `credits_required`, `sufficient_credits`, `lines`, `warnings`.
6. **Confirm the price with the user (STOP here)**: write a visible reply to the user: "This will cost N credits (balance B). Go?" and **end your turn**. Wait for their yes before `create_video`. Do not call `create_video` in the same turn as `estimate_video`, unless the user already approved a budget that covers N. `sufficient_credits: true` only means the balance is enough; it is **not** the user's approval, and neither is the original request. The price must appear in the chat reply, not only in your reasoning. If `sufficient_credits` is false, stop and send them to top up.
7. **Queue**: `create_video` with the same arguments plus `expected_credits: N` and a fresh `idempotency_key`. Save `workflow_id` and the key.
8. **Poll**: call `get_job` with `{ "workflowId": "…", "wait_seconds": 10 }` again and again until `completed` or `failed` ([polling](#polling)). The 10 s pause is built into the tool.
9. **Deliver**: hand over `video_url` (and `poster_url`), `credits_consumed`, and any warnings. On `failed`, act on `error_code` ([job failures](#job-failure-codes)).

**Edit a finished video** (each edit makes a NEW video; the source stays as the undo)
1. `get_scenes`: show the user the numbered scenes and their lines.
2. Pick the edit: one scene looks wrong → `fix_scene`; change words → `edit_script`; new voice-over or recording → `fix_sound`.
3. Call it with `dry_run: true` (no idempotency key needed, nothing charged), show `credits_quoted` (and the fix_sound `plan`), and get a yes.
4. Call it again with the same arguments without `dry_run`, plus `expected_credits: N` and a fresh `idempotency_key`. Poll the new `workflow_id` with `get_job` and `wait_seconds: 10`, then deliver.

## Hard rules

**Key handling**
1. The key lives only in Hermes: **set PROMOAT_KEY in Hermes; never paste it in chat.** If a tool returns `UNAUTHORIZED`, tell the user exactly that and wait. Never ask for the key, and never read, write, export or store it anywhere yourself.
2. If the user pastes a key into chat anyway, don't repeat it, and tell them to set it in Hermes instead. Recommend they get it replaced: there is no self-serve rotation for current keys, so they ask Promoat support.

**Spend safety**
3. Never call a paid tool without telling the user the price first, in a visible chat reply. For videos and edits, then wait for their yes (Golden path step 6); `sufficient_credits: true` is not approval. Videos: `estimate_video`. Edits: `dry_run: true`. Fixed prices (first frame 4, regenerate 4, TTS, clone 0 or 30) come from the [price list](#pricing). Instant tools have no `expected_credits` guard, so check `credits_charged` in the result.
4. Always send `expected_credits` = the price the user approved. If the server would charge more, it refuses with `QUOTE_MISMATCH` and charges nothing. A paid `fix_sound` **requires** it (missing = treated as 0 → `QUOTE_MISMATCH`).
5. Never loop on `INSUFFICIENT_CREDITS` or a 409-type code. `INSUFFICIENT_CREDITS`: report `credits_required` vs `credits_balance` and send the user to the dashboard's **Buy credits**. Other conflicts: read the code, re-quote or fix, and ask the user again.
6. Never re-queue a video while the original is still `queued`/`running`; that pays twice.
7. The delete tools (`delete_character`, `delete_voice`) are permanent. Confirm with the user before calling them.

**Retries and idempotency**
8. Send an `idempotency_key` on every `create_video` and every edit (edits require it). Use a new UUID per intended job and keep it in your notes.
9. On a `TRANSPORT` error, a timeout or `TRY_AGAIN`, repeat the **identical** call with the **same** key. You get the original job back (`"duplicate": true`) and nothing is charged twice. On `create_video` the request is re-validated and re-priced **before** the duplicate lookup. So a retry can instead get `QUOTE_MISMATCH` (the price rose: re-confirm, then resend with the new `expected_credits` under the same key) or `NOT_FOUND`/`INVALID_URL` (a referenced character, voice or recording is gone). Edits answer the duplicate first. Without a key, never blind-retry `create_video`: check `list_jobs` with `limit: 5` first.
10. A key is bound to its first job forever, even a failed one. A duplicate answer whose `status` is `failed` means "refunded, start over": use a **new** key for the new attempt.
11. Read-only tools (`get_*`, `list_*`, `estimate_video`, `plan_scenes`) are always safe to retry.

**Bookkeeping**
12. Record every id a tool returns (`character_id`, `voice_id`, `workflow_id`, `asset_id`/`frame_id`) and every idempotency key. Recover lost ids with `list_characters`, `list_voices`, `list_jobs`, `list_assets`.
13. Always tell the user about `warnings`: the request ran, but not exactly as written.

## Choosing the request

| The user wants… | Send to `estimate_video` / `create_video` | Price impact (768P) |
|---|---|---|
| One presenter talking to camera (promo, announcement, explainer, CTA) | `mode: "talking_head"` | 8 cr/s + first frame 4 + transcription |
| The presenter acting it out across shots (tour, demo, day-in-the-life) | `mode: "scenes"` (reference mode, default) | 8 cr/s + realistic photo 4 + photo/voice allowance + transcription |
| Scenes, cheapest, no photos needed | `mode: "scenes"`, `video_mode: "text"` | 4 cr/s, no photo line; scene photos and frames are ignored |
| A silent clip (music added later) | `mode: "scenes"`, `voice_mode: "none"`, `target_seconds` 5–60 (a number) | No TTS, no transcription; seconds = `target_seconds` |
| Presenter speaks a script in a chosen voice | `voice_id` + `script` | + TTS (10 per started 1,000 chars); priced at estimated length +10% (+35% non-Latin), settled at the real length, often with a refund |
| User has their own recording | `audio_url` (public https, 1–59.5 s) | Priced at the probed length; no TTS line |
| Captions burned in | `use_dynamic_captions: true` (talking head only) | +10 |
| Product / place / prop shots in the video | `scene_photos: [{url, role, caption}]` (≤3) | Talking head: used in the generated first frame, free. Scenes reference mode: allowance ≈ +0 / +0 / +6 / +10 for 0/1/2/3 photos on a 15 s video (grows with voiced clip length) |
| Lock the opening look before paying for the render | `create_first_frame` (4) → `first_frame_asset_id` | Drops the video's 4-credit frame line (net 0, but the look is approved first) |
| Their own opening still | `first_frame_url` (https, single subject) | −4 |
| Cheaper / sharper | `resolution`: `480P` / `768P` / `1080P` | 5 / 8 / 16 cr/s (text mode 2.5 / 4 / 8) |

Rules of thumb: `talking_head` is the safe default for a single message; use `scenes` when movement or real product shots matter. Scene `role`: `product` (the thing sold), `setting` (the place), `prop` (an object handled). `caption` (≤200 chars) says what it is. With no voice and no recording, only a silent `scenes` video is possible.

## First-run setup (tell the user)

1. **Account**: sign up at https://platform.promoat.ai/sign-up, then open the dashboard at https://platform.promoat.ai/partner.
2. **Buy credits**: dashboard → **Buy credits** → Stripe checkout. The default is the **$19.99 pack**: **1,499 credits** for accounts created on or after 8 July 2026 20:40 UTC (750 credits per $10), **1,738** for older accounts. A custom amount is available (multiples of 100 credits). Credits land within seconds.
3. **API key**: the first top-up creates the key. It is shown after checkout and can be copied from the dashboard's API key panel. Signing up from the homepage creates the key straight away, and 25 starter credits are added on the key's first call.
4. **Set PROMOAT_KEY in Hermes**: Hermes asks for it when the plugin is enabled. Never paste it in chat.
5. **Verify**: call `get_balance`. `UNAUTHORIZED` = the key is wrong, truncated or not set in Hermes.

For scale: a 15 s talking head at 768P from the user's own audio is 125 credits; a 15 s scenes video with 2 photos is 131.

## Writing the script (idea → approved script)

When the user brings an idea, not a script, do the creative work before any paid call:
1. Get the brief in one pass (skip what they already said): goal (sell / explain / announce / story), product or offer, audience, platform, length, language, tone, the one action viewers should take.
2. Offer three genuinely different hooks (direct benefit, curiosity gap, relatable problem), each sayable in the first 2–3 seconds. Let them pick or combine.
3. Recommend the format from the decision table in one sentence; let them override.
4. Write spoken language for the target length: ~35 words ≈ 15 s, 55–65 ≈ 25 s, 90–100 ≈ 40 s. Stay under ~120 words (~100 for Arabic and other non-Latin scripts); the hard cap is 59.5 s of speech. Structure: hook → one idea → one CTA.
5. For scenes, write concrete actions the same presenter can perform, and follow the identity rules in P7. Use the user's real product/place photos as `scene_photos`.
6. Optional: `plan_scenes` and show the scene lines; send approved lines back as `scene_lines`.
7. Show the full script and format for approval, then run the golden path from step 5.

Never claim facts were researched unless you actually checked a source. For medical, legal, financial or current-events claims, verify or ask the user for approved copy.

## Playbooks

Input URLs (selfies, samples, scene photos, frames, audio) must be **public https** URLs; private, link-local or metadata hosts are refused. All ids are scoped to the user's account: another account's id answers the same `NOT_FOUND` as a missing one.

### P1 — Character (free): `create_character`

- From selfies (reproduces the person): `{ "name": "Omar", "selfie_image_urls": ["https://cdn.example.com/omar-1.jpg"], "edit_instructions": "professional attire, studio lighting" }`
- From a description (invents a person): `{ "name": "Ava", "description": "a friendly presenter in her early 30s, warm smile", "reference_image_urls": ["https://cdn.example.com/mood.jpg"], "recast_attempt": 1 }`
- Result: `{ character_id, name, mode: "photos"|"description", sheet_image_url, character_sheet_text, asset_id, presenter_gender, head_covering, credits_charged: 0, warnings? }`
- `name` is required (≤120). Send exactly one of `selfie_image_urls` (https; first 3 used) or `description` (≤2,000). `edit_instructions` ≤500 (longer is cut). `reference_image_urls` (≤3, description mode only) are style inspiration, never an identity. Disliked face → re-run with `recast_attempt` 1, 2, … for a different person.
- A selfie or reference that can't be loaded is skipped with a `FIELD_IGNORED` warning; if no selfie loads, the call fails. Each video re-detects the head covering from the character image, so it is kept.
- **Regenerate the sheet** (same person, same `character_id`, **4 credits**): `regenerate_character` `{ "id", "edit_instructions"?: "navy blazer" }` → `{ character_id, sheet_image_url, asset_id, credits_charged }`.
- Manage: `list_characters`, `get_character`, `delete_character` (confirm first).

> `sheet_image_url` is a multi-pose reference sheet. Show it to the user, but never pass it as `first_frame_url`, or the video will animate the grid. Pass `character_id`; to control the opening look use P4.

### P2 — Voice

- **Studio voices** (free, multilingual): `list_voice_presets` → `{ voices: [{ studio_voice, gender, languages }] }`. Add one with `clone_voice` `{ "name": "Spanish narrator", "language": "spanish", "gender": "female", "studio_voice": "Sarah" }` → `{ voice_id: "sv_…", kind: "library", credits_charged: 0, … }`.
  - Send `language` and/or `studio_voice`, not `sample_urls`. Never send `language` together with `sample_urls` ("Provide exactly one voice source"); for a clone in another language use `preview_language`.
  - Voices: male Brian, Daniel, George, Chris; female Sarah, Laura, Alice, Jessica. Without `studio_voice`, one is picked from `gender` (default `female`). An unknown name → `INVALID_STUDIO_VOICE`. Cap: 10 library voices.
- **Clone a real voice**: `clone_voice` `{ "name": "Ava voice", "sample_urls": ["https://cdn.example.com/ava-1.mp3"], "preview_language": "en" }` → `{ voice_id: "pv_…", kind: "cloned", credits_charged, preview_url, warnings }`.
  - `name` ≤80. Send 1–25 public https `sample_urls` of clean speech (25 s+ total is best).
  - The **first** clone per account is free, once ever (deleting it does not reset that); later clones cost 30. Tell the user "free if it is your first clone, otherwise 30". There is no `expected_credits` guard, so read `credits_charged`.
  - Under ~25 s of usable speech → warning `LOW_SAMPLE_AUDIO` (offer a re-clone). Play `preview_url` to the user. Cap: 3 cloned voices.
- Clone errors:
  - `sample_errors: [{index, reason}]`: no sample could be fetched.
  - `INVALID_SAMPLES`.
  - `NO_SPEECH`: refunded.
  - `CLONE_UNAVAILABLE`: retry later, refunded.
  - `VOICE_LIMIT_REACHED` (+`max_voices`): delete one.
  - `FREE_CLONE_ATTEMPTS_EXHAUSTED`: the free clone failed 20 times. Fix the samples and ask Promoat support; don't retry.
- **Re-clone** (better samples, or revive an expired clone): `reclone_voice` `{ "id", "sample_urls": [...], "preview_language"?: "en" }` → `{ voice_id: "pv_NEW…", previous_voice_id, … }`. It gets a new id and the old one is removed, so update your notes. Costs 30, or **0** if the old voice had expired. A studio voice → `NOT_A_CLONED_VOICE`.
- Manage: `list_voices`, `delete_voice` (frees a slot; confirm first).

### P3 — Text-to-speech (standalone audio): `synthesize_speech`

- Arguments: `{ "voice_id", "text": "Welcome back! Here is what is new this week.", "language": "en", "voice_settings": { "stability": 0.5, "similarity_boost": 0.75, "style": 0.3, "speed": 1.1 } }` → `{ audio_url, duration_sec, asset_id, credits_charged, characters }`.
- `text` ≤5,000 chars. `language` is a name or ISO code, and wins over the older `language_code`. Settings are clamped: `speed` 0.7–1.2, others 0–1.
- **Price: max(10, ceil(chars / 1,000) × 10)**.
- An expired or removed voice → `VOICE_UNAVAILABLE` with `voice_state` (re-clone, P2).
- For videos you don't need this: pass `voice_id` + `script` to `create_video`. A TTS asset can be reused as a `fix_sound` take (`tts_asset_id`).

### P4 — First-frame still (4 credits): `create_first_frame`

- `{ "character_id", "kind": "talking_head", "scene_description": "behind the counter of a bright coffee shop, morning light" }` → `{ image_url, asset_id, frame_id, kind, credits_charged: 4, warnings? }`
- `kind`: `talking_head` (default) or `moving_scene` (the realistic photo a scenes video starts from).
- One of `scene_description` (≤2,000), `scene_prompt` (≤400) or `script` (≤4,000, context only) is required. `scene_photos` (≤3) are used for `talking_head` frames only. `language` is optional.
- Pass `frame_id` to `create_video` as `first_frame_asset_id`. The look is locked and the video drops its own 4-credit frame line. The kind must match the video mode, else `FIRST_FRAME_KIND_MISMATCH`.
- Failure (refunded): `FIRST_FRAME_NOT_VERTICAL` (retry), `CHARACTER_IMAGE_UNAVAILABLE` (regenerate the character), `PROVIDER_*` or `INTERNAL`.

### P5 — Talking-head video: `estimate_video` → confirm → `create_video`

Example arguments:
```json
{
  "mode": "talking_head",
  "character_id": "CHARACTER_ID",
  "voice_id": "VOICE_ID",
  "script": "Hi! Three quick updates from the shop this week. First, we extended our opening hours.",
  "video_idea": "standing in a bright modern kitchen, smiling at the camera",
  "resolution": "768P",
  "use_dynamic_captions": true,
  "captions_position": "bottom"
}
```

- `estimate_video` returns `{ mode, credits_required, credits_balance, sufficient_credits, estimated_seconds, billed_seconds, resolution, job_type, price_table_version, lines, clips, breakdown, warnings }`.
- After the user approves `credits_required`, call `create_video` with the same arguments plus `"expected_credits": <credits_required>` and `"idempotency_key": "<new UUID>"`. Result: `{ workflow_id: "partner_h3t_…", status: "queued", credits_reserved, credits_quoted, …, duplicate: false }`.
- `character_id` is required on `create_video`. The estimate prices without it and doesn't check ids, so `NOT_FOUND` or `FIRST_FRAME_KIND_MISMATCH` may first appear on `create_video`.
- Audio: exactly one of `voice_id` + `script` (≤4,000 chars, spoken verbatim) or `audio_url` (P6). Speech must be 1–59.5 s (`AUDIO_TOO_SHORT` / `AUDIO_TOO_LONG`); 1–5 s bills as 5.
- `video_idea` (≤2,000) is required unless a frame is given: `first_frame_asset_id` (a `talking_head` frame from P4) or `first_frame_url`, not both. `scene_prompt` (≤400) and `scene_photos` also shape the generated frame.
- `resolution`: `480P`, `768P` (default) or `1080P`, any case. `720p` is served as 768P with `RESOLUTION_MAPPED`; anything else → `INVALID_RESOLUTION`. `video_mode` and `voice_mode: "none"` are refused on talking heads.
- Other options:
  - `voice_settings` (as P3) and `language` (name or ISO code).
  - `scene_lines`: from P8; 1–15 strings ≤600 chars.
  - `topic` / `audience`: accepted but have **no effect** (`FIELD_IGNORED`). Put the brief in `video_idea` / `scene_prompt`.
- Captions:
  - `use_dynamic_captions: true` (+10) burns word-by-word captions on a solid band.
  - `captions_position`: `bottom` (default), `center` or `top`. Pick a frame that leaves that area clear.
  - `captions_language` is an optional hint (`"en"`, `"ar"`).
- `expected_credits` must be a whole number ≥0. A higher server quote → `QUOTE_MISMATCH` (+`credits_quoted`), and nothing is charged.
- Accepted but ignored (`FIELD_IGNORED`): `fast`, `narration_mode`, `topic`, `audience`, and a non-https `first_frame_url` / `audio_url`. Every talking head is lip-synced automatically.

### P6 — From the user's own recording

Replace `voice_id` + `script` with `"audio_url": "https://cdn.example.com/narration.mp3"` (talking head or scenes).
- The length is probed server-side; a private or unreadable URL → `INVALID_URL`. The same 1–59.5 s rule applies.
- Recording-voiced videos can't use `edit_script` later (only `fix_scene` / `fix_sound`).

### P7 — Scenes video (the presenter acts the script out)

> **Identity rules for `video_idea` / `scene_prompt`**: state the presenter's gender and lock to one person, e.g. `one female barista, the same woman throughout; no other people; do not restyle or recast the presenter`. Describe the presenter *doing* things ("pours", "holds up the bag"), not a scene full of people.

Example arguments:
```json
{
  "mode": "scenes",
  "character_id": "CHARACTER_ID",
  "voice_id": "VOICE_ID",
  "script": "Ever wondered how we roast our beans? Come on, I will show you. This is where every batch starts.",
  "scene_lines": ["Ever wondered how we roast our beans?", "Come on, I will show you.", "This is where every batch starts."],
  "video_idea": "one female barista, the same woman throughout, touring a small roastery. Single presenter only.",
  "scene_prompt": "warm industrial roastery, morning light, sacks of green coffee",
  "video_mode": "reference",
  "resolution": "768P",
  "scene_photos": [
    { "url": "https://cdn.example.com/retail-bag.jpg", "role": "product", "caption": "our 250g retail bag" },
    { "url": "https://cdn.example.com/storefront.jpg", "role": "setting", "caption": "the shop exterior" }
  ],
  "language": "english"
}
```
Then follow the same flow: `estimate_video` → confirm → `create_video` with `expected_credits` and `idempotency_key` (`workflow_id` `partner_h3v_…`).
- `mode`: `scenes` (alias `moving_scene`). Audio: `voice_id` + `script`, or `audio_url`, or none with `voice_mode: "none"`.
- `video_mode`:
  - `reference` (default): the presenter's realistic photo plus up to 3 scene photos; voiced clips are spoken on camera.
  - `text`: half price; scene photos and frames are ignored with `FIELD_IGNORED`.
- `voice_mode: "none"` (silent):
  - `target_seconds` 5–60 is required, as a **number** (`"15"` → `INVALID_DURATION`).
  - The brief is `script`, else `scene_lines`, else `video_idea`; one is required.
  - `audio_url` is refused; `voice_id` is ignored.
- `scene_photos`: `[{ url, role?, caption? ≤200 }]`. The first 3 unique URLs are used (`SCENE_PHOTOS_TRUNCATED`); more than 12 items or a malformed item → `INVALID_SCENE_PHOTOS`. A photo that can't be fetched at render time is dropped and the charge re-quoted without it (never above the reservation); the job carries `SCENE_PHOTO_DROPPED` in its `list_jobs` row → `metadata.warnings`.
- `first_frame_asset_id`: a `moving_scene` frame (P4); a talking-head frame → `FIRST_FRAME_KIND_MISMATCH`. Or use `first_frame_url`. Either drops the 4-credit photo line.
- `scene_prompt`, `scene_lines`, `language`, `voice_settings` and `resolution` work as in P5. `use_dynamic_captions` has no effect on scenes.

### P8 — Scene plan (free, instant): `plan_scenes`

- `{ "video_type": "scenes", "script": "Ever wondered how we roast our beans? ..." }` → `{ scenes: [{ index, line, seconds }], max_words_per_scene }`
- `video_type`: `talking_head`, `scenes`, `moving_scene` or `normal_video` (the last two are aliases of `scenes`). `script` 1–4,000 chars.
- Optional: `audio_duration_seconds` (≤60.5; required and 5–60 with `voice_mode: "none"`) and `voice_mode`.
- `max_words_per_scene` is 32 for talking heads and 33 for scenes.

### P9 — Edits: `get_scenes`, then `fix_scene` / `edit_script` / `fix_sound`

General rules for all three:
- **Source video:** pass its `workflowId`. It must be `completed`, and its `get_job` `result.editable` must be `true`. An edit's output can be edited again.
- **Extra fields:** `fix_scene` and `edit_script` refuse fields beyond those listed (`INVALID_BODY`). **`fix_sound` silently ignores unknown fields**, so spell `expected_credits` and `dry_run` exactly; a typo reads as missing → `QUOTE_MISMATCH`.
- **Idempotency:** `idempotency_key` (or `client_request_id`) is **required** unless `dry_run: true` (`IDEMPOTENCY_KEY_REQUIRED`). Edit keys are per account and per tool, not per source video.
- **Limits:** edits count toward the 5 active jobs. Only one open edit per source video (`EDIT_IN_PROGRESS`); an edit idle for 30 min no longer blocks.

`get_scenes` returns `{ workflow_id, video_type, resolution, editable, voice: { source: "ai_voice"|"recording"|"none" }, poster_url?, scenes: [{ index, line, seconds, start_seconds, talks, clip_url?, poster_url? }], source_workflow_id? }`.

- **`fix_scene`** `{ workflowId, scene_index (0–99), description? ≤500 }`
  - Talking head: no description = a new take (`new_take`); with a description = a new frame for that scene (`new_frame`, +4).
  - Scenes: `description` is required (`visual_fix`, else `FIX_TEXT_REQUIRED`).
  - An index the video doesn't have → `INVALID_SCENE`.
  - Dry run → `{ dry_run: true, credits_quoted, credits_balance, sufficient_credits, lines, edit_kind, … }`. Run → `{ workflow_id: "partner_se_…", status: "queued", … }`.
- **`edit_script`** `{ workflowId, lines: [{ scene_index, line ≤600 }] }` (1–20 lines)
  - Spoken in the video's own AI voice. Only changed lines are re-made, each +TTS.
  - Errors: nothing changed → `NO_CHANGES`; a line longer than one scene → `LINE_TOO_LONG` with `max_words`; empty line → `EMPTY_LINE`; unknown or duplicate index → `INVALID_SCENE`.
  - Videos voiced by a recording, silent, or already sound-fixed → `VOICE_EDIT_UNAVAILABLE` (use `fix_sound`).
- **`fix_sound`**: exactly one take, `{ audio_url }`, `{ tts_asset_id }` (an asset from P3), or `{ voice_id, script ≤4,000, voice_settings?, language? }`.
  - Dry run → `{ dry_run, plan: "swap_audio"|"regenerate", credits_quoted, lines, video_ms, … }`. Run → `{ workflow_id: "partner_fs_…", plan, … }`.
  - `swap_audio` (**free**): a scenes video with no on-camera talking whose new recording is within ±300 ms of the video length; the sound is simply replaced.
  - `regenerate` (paid, needs `expected_credits`): every talking head, any scenes video with on-camera talking, and any other length. The video is remade at the take's length. A `voice_id` + `script` take is always quoted as `regenerate`.
  - Take too short (under 1 s or under 40% of the video) → `TAKE_TOO_SHORT`; over 59.5 s → `TAKE_TOO_LONG` (both with `video_ms`).
- Other edit errors: `NOT_FOUND`, `VIDEO_NOT_READY`, `VIDEO_NOT_EDITABLE` (made before 1.1.0 or without scene data), `QUOTE_MISMATCH`, `IDEMPOTENCY_KEY_REUSED`, `INSUFFICIENT_CREDITS`, `TOO_MANY_ACTIVE_JOBS`, `TRY_AGAIN`, `START_FAILED` / `INTERNAL` (refunded).

### P10 — Account, history, assets (all free)

- `get_balance` `{ "from": "2026-10-01T00:00:00Z", "to": "2026-10-03T00:00:00Z" }` → `{ credits_balance, credits_balance_base, credits_spent_lifetime, credits_consumed_in_range, job_counts: { completed, failed, running_or_queued, total_in_range }, from, to }`. The default range is this UTC month. `credits_spent_lifetime` = spend since the LAST TOP-UP (it resets at each top-up), not all-time spend.
- `list_jobs` `{ "limit": 30, "offset": 0 }` → `{ jobs: [{ workflow_id, status, job_type, credits_estimated, credits_actual, queued_at, completed_at, error_message, metadata }] }`. Also lists non-video rows (`character_sheet`, `tts`, `voice_clone`, `first_frame_image`, `voice_library`).
- `list_assets` `{ "kind": "video", "limit": 30 }` → `{ assets: [{ asset_id, kind, url, workflow_id, character_id, voice_id, metadata, created_at }] }`; `get_asset` `{ id }` for one. `kind`: `character_sheet`, `first_frame`, `tts_audio` or `video`.
- Lists are newest first; `limit` defaults to 30 and is capped at 100.

## Polling

Call `get_job` `{ "workflowId": "…", "wait_seconds": 10 }` repeatedly until `status` is `completed` or `failed` (`wait_seconds: 30` is fine after 10 minutes). Show `phase`/`progress` to the user as it moves.

- **The wait is built into `get_job`.** `wait_seconds` (0–30) makes the plugin pause before checking, so every call is one poll spaced 8–10 s apart. It is handled inside the plugin and is not sent to Promoat.
- **Always poll with the `get_job` tool itself.** Never use `execute_code`, `terminal`, `sleep`, `time.sleep`, curl, `urllib` or any script to wait or poll, and never call a REST endpoint like `/jobs/{id}/status`. Those need the user to click Run for every pause. `get_job` is a normal `promoat` tool and is not available inside `execute_code`, so do not look for it there.
- **Never ask the user to run, click or confirm anything to continue polling.** Keep calling `get_job` until the job ends.

- **Fields**:
  - `workflow_id`, `status` (`queued`/`running`/`completed`/`failed`), `job_type`.
  - `phase` (queued → preparing → generating → assembling → finalizing → completed/failed) and `progress` (0–100 or null).
  - Output: `video_url`, `image_url`, `poster_url`, `source_workflow_id`.
  - Credits: `credits_estimated`, `credits_actual`, `credits_consumed`.
  - Failure: `error_code`, `error_message`.
  - Also `result`, `queued_at`, `completed_at`.
  - On completion `result` may hold `video_url`, `asset_id`, `poster_url` and `editable`. Use `get_scenes` for the scene list.
- **Expect**: talking head ~10 min, scenes ~25 min. Edits take about as long as their source type; a free sound swap is quick. If a job runs longer, keep polling and tell the user it is slow; don't re-queue. A job with no progress for **75 minutes** is failed with `STALE_TIMEOUT` and refunded automatically.
- **`completed`**: deliver `video_url` (+`poster_url`), `credits_consumed` (≤ the reservation; script jobs often get a refund), and any warnings (the job's `list_jobs` row → `metadata.warnings`). Offer edits if `result.editable`.
- **`failed`**: the reservation is refunded once, automatically. Show `error_message` (user-safe) and act on `error_code` below.
- `NOT_FOUND`: wrong id or another account's job. Recover it from `list_jobs`.

### Job failure codes

| `error_code` | Do this |
|---|---|
| `PROVIDER_MODERATION` | Content refused. Rephrase `video_idea` / `scene_prompt` / the fix `description`, or use other photos; don't resend the same request |
| `PROVIDER_INPUT` | A photo or audio file could not be used. Replace it (or regenerate the character) and re-queue |
| `PROVIDER_INFRA`, `PROVIDER_TIMEOUT`, `START_FAILED`, `INTERNAL`, `STALE_TIMEOUT` | Transient. Re-queue **once** with a **new** key (after re-confirming the price); if it fails again, stop and report |
| `LINE_TOO_LONG` | Shorten the offending line(s) to ≤ `max_words_per_scene` (P8) and re-queue |
| `VOICE_UNAVAILABLE` | Voice expired/removed: `reclone_voice` (free if expired) or pick another voice; re-queue with the new id |
| `FIX_NOT_APPLIED` | The edit could not be applied: reword the fix `description` and retry |
| `MISSING_ASSET` | Something the job needed is gone (e.g. the source video): make the video again with `create_video` |
| `AUDIO_TOO_LONG` | The real speech ran over 59.5 s: shorten the script and re-queue |

## Idempotency

- `idempotency_key` takes 1–255 visible ASCII characters (a UUID is ideal); `client_request_id` must be a UUID. If both are sent and differ → `IDEMPOTENCY_KEY_MISMATCH`; a malformed key → `IDEMPOTENCY_KEY_INVALID`.
- It is optional on `create_video` and required on `fix_scene` / `edit_script` / `fix_sound` (except with `dry_run`).
- Same key + same request → `{ workflow_id, status, duplicate: true, credits_reserved }`: the original job, never a second charge, whatever its status. On `create_video`, validation and the price check run first (see rule 9); edits answer the duplicate first.
- Same key + different request → `IDEMPOTENCY_KEY_REUSED`. `expected_credits`, warnings and ignored fields don't count toward "different", and `"720p"` equals `"768P"`.
- One key covers all `create_video` modes. Keys are per account and per tool.
- `INSUFFICIENT_CREDITS`, `TOO_MANY_ACTIVE_JOBS` and `QUOTE_MISMATCH` create no job: after topping up, waiting or re-confirming, the same key is still usable.

## Pricing

Price table **2026-09-30** (`price_table_version` in results). A deployment may add a markup, so always quote the `estimate_video` / `dry_run` number, never this table.

| Item | Credits |
|---|---|
| Character create · studio voice · scene plan · estimate · reads | 0 |
| Character regenerate · first frame / realistic photo | 4 |
| TTS | max(10, ceil(chars / 1,000) × 10); 600 chars = 10, 1,001 = 20 |
| Voice clone | first per account 0, then 30 · re-clone 30 (0 if expired) |
| Dynamic captions (talking head) | 10 |
| Transcription line (voiced videos) | ceil(seconds / 20) |

**Generation, credits per second** (talking head billed on whole seconds; scenes on whole 5–15 s clips)

| Resolution | Talking head | Scenes reference | Scenes text |
|---|---|---|---|
| 480P | 5 | 5 | 2.5 |
| 768P | 8 | 8 | 4 |
| 1080P | 16 | 16 | 8 |

Quote `lines[].kind`: `generation`, `first_frame` (dropped with the user's own frame), `reference_allowance` (scenes reference mode), `transcription` (not on silent videos), `tts` (script mode), `captions`, `product` (a fix_sound swap, 0).

**Worked examples** (768P, own audio unless noted)

| Video | Credits |
|---|---|
| 15 s talking head | 125 (120 + frame 4 + transcription 1) |
| 15 s talking head, own frame | 121 |
| 15 s talking head + captions | 135 |
| 15 s talking head at 480P / 1080P | 80 / 245 |
| 5 s talking head at 480P | 30 |
| 59.5 s talking head | 487 |
| ~35-word script (≈17 s quoted) talking head | 151 (incl. TTS 10) |
| 15 s scenes, reference, 0 / 2 / 3 photos | 125 / 131 / 135 |
| 15 s scenes, text mode | 61 |
| 15 s silent scenes, reference / text | 124 / 60 |
| Fix-scene, 8 s talking-head scene: new take / new frame | 64 / 68 |
| Fix-sound, new 15 s recording on a talking head | 121 |
| Fix-sound swap on a scenes video (fits ±300 ms) | 0 |

**Charging**: the quote is reserved when the job starts and acts as a ceiling. The final charge is min(actual, reserved), and the rest is refunded on completion. Failures refund once, automatically. Instant tools (characters, regenerate, voices, TTS, first frame) charge once, return `credits_charged`, and refund on failure. Nothing is charged for a request that fails validation, auth or the balance check.

## Limits

| Limit | Value | Signal |
|---|---|---|
| Active video jobs + edits (queued + running) | 5 | `TOO_MANY_ACTIVE_JOBS` (+`max_active_jobs`) |
| Cloned voices / library voices | 3 / 10 | `VOICE_LIMIT_REACHED` (+`max_voices`) |
| Voiced video audio | 1–59.5 s (1–5 s bills as 5) | `AUDIO_TOO_SHORT` / `AUDIO_TOO_LONG` |
| Silent scenes `target_seconds` | 5–60 s | `INVALID_DURATION` |
| Video / fix_sound script | 4,000 chars | `INVALID_SCRIPT` |
| `video_idea` · `scene_prompt` | 2,000 · 400 chars | `INVALID_BODY` |
| `scene_lines` | 1–15, each ≤600 chars | `INVALID_SCENE_LINES` |
| Scene photos | 3 used, ≤12 sent, caption ≤200 | `SCENE_PHOTOS_TRUNCATED` / `INVALID_SCENE_PHOTOS` |
| TTS text | 5,000 chars | error |
| Selfies / reference images | first 3 used | extras ignored |
| Voice samples per clone | 1–25 | error when none is usable |
| Edit lines | 1–20, each ≤600 chars; scene index 0–99 | `INVALID_BODY` |
| Open edits per source video | 1 (an edit idle for 30 min no longer blocks) | `EDIT_IN_PROGRESS` |
| Quiet job | 75 min | failed `STALE_TIMEOUT`, refunded |
| List page | `limit` ≤100 (capped) | — |

## Errors

A failed tool call returns `{ "error_code": "UPPER_SNAKE", "message": "human-readable", … }`, sometimes with `field`. **Branch on `error_code`.** Extra details may include `credits_required`, `credits_balance`, `credits_quoted`, `plan`, `max_active_jobs`, `max_voices`, `max_words`, `video_ms`, `voice_state` and `sample_errors`. Two codes come from the plugin itself: `TRANSPORT` (network problem: retry with the same idempotency key) and `CLIENT_ERROR` (the request was rejected: read `message`).

| Code | Do this |
|---|---|
| `INVALID_BODY`, `INVALID_RESOLUTION`, `INVALID_VIDEO_MODE`, `INVALID_VOICE_MODE`, `INVALID_DURATION`, `INVALID_SCRIPT`, `INVALID_SCENE_LINES`, `INVALID_SCENE_PHOTOS`, `INVALID_VOICE_SETTINGS`, `INVALID_STUDIO_VOICE`, `NOT_A_CLONED_VOICE`, `INVALID_SAMPLES` | Fix the named `field` and resend (no charge happened) |
| `INVALID_URL` | Use a public, reachable https URL with real content |
| `AUDIO_TOO_SHORT` / `AUDIO_TOO_LONG` | Speech must be 1–59.5 s: lengthen or shorten the script/recording |
| `FIRST_FRAME_KIND_MISMATCH` | Make a frame with the matching `kind` (P4) |
| `IDEMPOTENCY_KEY_REQUIRED` / `_INVALID` / `_MISMATCH` | Add a key / send 1–255 visible ASCII (or a UUID `client_request_id`) / make the two agree |
| `FIX_TEXT_REQUIRED`, `INVALID_SCENE`, `NO_CHANGES`, `EMPTY_LINE`, `LINE_TOO_LONG` (+`max_words`), `VOICE_EDIT_UNAVAILABLE` | Fix the edit request (P9); for a recording-voiced video use `fix_sound` |
| `TAKE_TOO_SHORT` / `TAKE_TOO_LONG` (+`video_ms`) | Use a take between 40% of the video length (≥1 s) and 59.5 s |
| `UNAUTHORIZED` | The key is missing or wrong: ask the user to set PROMOAT_KEY in Hermes. Never ask for it in chat |
| `INSUFFICIENT_CREDITS` (+`credits_required`, `credits_balance`) | Tell the user the gap; dashboard → Buy credits; then resend (same key OK). Don't loop |
| `NOT_FOUND` (+`field`) | The id is wrong or not this account's; recover it with the `list_*` tools |
| `QUOTE_MISMATCH` (+`credits_quoted`) | The price went up: show the new price, get a yes, resend with the new `expected_credits` |
| `IDEMPOTENCY_KEY_REUSED` | You changed the request under an old key: use a new key for a new job |
| `VOICE_LIMIT_REACHED` (+`max_voices`) | Delete an unused voice of that kind (with the user's OK), then retry |
| `FREE_CLONE_ATTEMPTS_EXHAUSTED` | Stop retrying; fix the samples and contact support |
| `VOICE_UNAVAILABLE` (+`voice_state`) | Re-clone (P2) or pick another voice |
| `VIDEO_NOT_READY` | Wait until the source job is `completed` |
| `VIDEO_NOT_EDITABLE` | This video can't be edited (older engine / no scene data): make a new one |
| `EDIT_IN_PROGRESS` | Wait for the open edit of this video to finish |
| `NO_SPEECH` | Supply clear speech samples |
| `TOO_MANY_ACTIVE_JOBS` (+`max_active_jobs`) | Wait for a job to finish (keep polling), then resend with the same key |
| `START_FAILED` / `INTERNAL` | Refunded. Resend once; if the answer is a duplicate with `status: "failed"`, use a new key |
| `FIRST_FRAME_NOT_VERTICAL`, `PROVIDER_*` | Refunded. Retry once |
| `CHARACTER_IMAGE_UNAVAILABLE` | Regenerate the character |
| `CLONE_UNAVAILABLE` | Cloning is briefly unavailable: retry in a few minutes (refunded) |
| `TRY_AGAIN` | Nothing charged: retry after a few seconds with the same key (up to ~3 times) |

**Warnings** (`warnings: [{ field, code, message }]` on a successful result):
- `RESOLUTION_MAPPED`: 720p was served as 768P.
- `FIELD_IGNORED`: a legacy or non-applicable field was ignored, e.g. `topic`/`audience`, a non-https URL, an unloadable selfie, photos or a frame in text mode, or `voice_id` on a silent video.
- `SCENE_PHOTOS_TRUNCATED`: only 3 photos were kept.
- `LOW_SAMPLE_AUDIO`: the clone came from under 25 s of speech.
- `SCENE_PHOTO_DROPPED`: raised at job time, on the job's `list_jobs` row.

Always relay warnings to the user.

## Troubleshooting

- **Quote too high**: read `lines`. Drop to 480P, shorten the script, skip captions, use an approved frame of the user's own, or use scenes with `video_mode: "text"`.
- **User dislikes the face**: description mode, bump `recast_attempt`; selfie mode, use better-lit selfies or `regenerate_character` with `edit_instructions`.
- **Wrong language/accent**: set `language` on the video / TTS. Studio voices are multilingual and free.
- **`NOT_FOUND` on a voice just used**: re-clones get a new id; check `list_voices`.
- **One scene is wrong**: use `fix_scene`, not a whole new video.
- **Want another take of the same video**: re-queue with a **new** key (each job is an independent generation); vary `video_idea` for a different setting.
- **Ids from before 1.1.0** keep working; videos made before 1.1.0 can't be edited.
