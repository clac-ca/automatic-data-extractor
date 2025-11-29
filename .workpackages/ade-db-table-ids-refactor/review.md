You’re basically solving three problems at once here:

1. **Human readability / type disambiguation** (prefixes),
2. **Time ordering** (sortable IDs),
3. **Having exactly one ID per resource across DB/API/storage/logging.**

I’ll first challenge your proposed “OpenAI‑style timestamped hex” design from a few angles, then propose what I’d consider the most standard, least‑surprising design for ADE, plus how I’d roll it out.

---

## 1. Challenge: is the proposed format actually “standard”?

You propose:

> `<prefix>_<payload>` where payload is a 24‑byte, timestamp‑first hex string (48 lowercase hex chars). First 4 bytes encode epoch seconds, remaining bytes random. Columns sized to `String(60)`.

Architecturally, this is **custom**:

* 24 bytes (192 bits) is **not** a common size.
* 4‑byte (32‑bit) UNIX seconds timestamp has the same “year 2106” problem as old 32‑bit `time_t`.
* 48‑char hex with 24‑byte payload is not ULID, not UUID v7, not Snowflake. It’s “your own thing”.

That’s not inherently bad, but it’s *not* “most standard / most common”. Today, the “standard” ID patterns you see in the wild are:

* **UUIDv4 / v1 / v7** (128 bits). v7 is the new time‑ordered standard.
* **ULID** (128 bits), widely used in app code.
* **Snowflake‑like 64‑bit integers** (Twitter, etc.) for extreme scale.

All of those already solve:

* Time‑ordered IDs,
* Encoded timestamp for debugging,
* Collision resistance with random bits.

So the big question: **what are you getting from 24‑byte timestamped hex that you don’t get from ULID or UUIDv7?**

If the answer is “we like how OpenAI’s IDs look”, I’d strongly consider **emulating the shape (prefix + opaque token)** rather than their exact bit‑layout. Reinventing the payload format:

* Forces you to write/maintain custom generators in every language (Python, TS, maybe Go/Rust later).
* Introduces subtle risks (endian bugs, timestamp truncation, time‑sort bugs, off‑by‑one around epoch, etc.).
* Gives little practical benefit over a standard 128‑bit time‑ordered ID.

### Suggestion

If you want to be “standard” and boring:

* **Pick a well‑known time‑ordered 128‑bit ID** (ULID or UUID v7).
* Wrap it in a string prefix: `ws_<payload>`, `run_<payload>`, etc.
* Don’t invent a 192‑bit tshex with 4‑byte seconds unless you have a very strong reason.

Given you already have `generate_ulid()` and ULID‑backed tables, the path of least surprise is:

> **Canonical format:** `<prefix>_<ulid>` where `<ulid>` is a standard 26‑char ULID (Crockford base32).
> Column size: `String(40)` (prefix + underscore + 26 chars + some headroom).

That keeps:

* Time ordering semantics,
* Existing ULID tools & understanding,
* Minimal DB index bloat.

If you prefer UUIDv7, the equivalent is:

> `<prefix>_<uuid7hex>` where `uuid7hex` is 32 hex chars (128 bits).
> Column size: `String(45)` is plenty.

---

## 2. Challenge: single canonical ID vs decoupled “public IDs”

You explicitly state:

> **Shared across layers for the same resource (must stay identical across DB/API/storage/logging)**: workspace_id, configuration_id, document_id, build_id, run_id, api_key_id…

This is **not the most common pattern** in mature systems.

Typical large systems do:

* An internal **surrogate key** (int, UUID, ULID) as the DB primary key.
* A separate **public ID** or **external ID**:

  * Often prefixed (`ws_...`, `run_...`),
  * Sometimes derived from the internal ID, sometimes completely independent.

Benefits of decoupling:

* You can change external format without rewriting DB PKs.
* You can rotate public IDs (e.g. if they leaked) without touching relational integrity.
* You can have short, index‑friendly PKs and more descriptive public IDs.

Right now you’re “all‑in” on:

> `id` is both the relational key and the public, human‑visible identifier.

That’s workable, but it dramatically increases the cost of any future ID format change. You’re feeling that pain already with this work package.

### Reasonable compromise

Given where ADE is:

* If you **really do not** have any production DB yet → you can be more aggressive and design this cleanly once.
* If you *might* already have prod / staging data → I would seriously consider:

  * Keep existing `id` as the **DB PK** (ULID or whatever).
  * Introduce a `public_id` (unique) with prefixes and time‑ordering semantics.
  * Use `public_id` in APIs, URLs, storage paths, logs.
  * Keep DB joins on `id`.

This is the most common “standard” architecture.

If you really want to stick with “one ID everywhere”, be aware you’re choosing convenience now at the cost of **hard migrations every time you tweak ID design**.

---

## 3. Challenge: column sizes & schema footprint

You propose bumping everything to `String(60)`.

Concerns:

* **Index bloat**: PK & FK indexes on 60‑char `VARCHAR` are bigger and slower to traverse than 32–40‑char columns.
* **Inconsistency**: Some tables currently use `String(26)` and others `String(40)`; moving everything to 60 is simple but maybe over‑allocating.

If you use:

* ULID (26 chars) + `prefix_` (say max 8 chars + `_`) → worst case ~35 chars.
* UUIDv7 hex (32 chars) + `prefix_` → worst case ~39 chars.

Then a **uniform `String(50)`** is generous and still smaller than 60, or even `String(40)` if your prefixes are short (which they are).

Not a massive deal, but if you care about index size and buffer cache efficiency, it’s worth tightening.

**Suggestion:**

* Decide on a **realistic max prefix length** (e.g. 8 chars).
* Choose ULID or UUIDv7.
* Set `id` and FKs to `String(40)` or `String(50)` instead of 60.

---

## 4. Challenge: custom timestamp layout (4‑byte seconds)

Architectural issues with: “first 4 bytes encode epoch seconds”:

1. **Year‑2106 cliff**: 32‑bit seconds from 1970 runs out around 2106. Maybe not your problem, but it’s self‑inflicted if you have a clean slate.
2. **One‑second granularity**: If you care about ordering within the same second (high‑throughput inserts), you’ll rely on randomness for tie‑breaking and may lose strict monotonic order, which ULID/UUIDv7 already handle better.
3. **You have to pick an endianness** and get it right everywhere; mistakes mean time ordering is broken.

Standard schemes (ULID, UUIDv7) use:

* **48 bits of timestamp** (ms precision) → ~8,900 years of range,
* Clear, well‑tested layouts and monotonic generation strategies.

Given your goal is just “time‑ordered IDs and easy debugging”, **rolling your own binary layout is unnecessary complexity**.

---

## 5. Challenge: migration story & mixed formats

You explicitly have an open question:

> Should we allow mixed legacy formats during transition (ULID/UUID4 + new timestamped hex), or backfill everything?

From an architectural / operational POV:

* **Backfilling PKs is brutal** once there’s real data:

  * Every FK link must be updated.
  * Path names in storage, log entries, webhook payloads, etc. may embed old IDs.
  * You risk long migrations, lock contention, and subtle broken references.

* **Mixed formats are normal** in grown systems:

  * Old rows have legacy IDs.
  * New rows use the new format.
  * Validators accept both patterns; over time legacy gets proportionally small.

Unless you are 100% sure there is **no prod data, no external integrations, and no durable paths using existing IDs**, I’d strongly recommend:

> **Accept mixed formats forever and never rewrite existing IDs.**

Architecturally, that means your validators and ID helpers should:

* Know how to **recognize prefixes** and the new payload format.
* **Fall back** to “legacy opaque string” if the value doesn’t match the new pattern but still fits column length.

---

## 6. A more “standard” design I’d recommend for ADE

Taking your goals and constraints into account, here’s what I’d actually do.

### 6.1 Core decision: use ULID + prefixes (or UUIDv7 + prefixes)

Because:

* You already use ULID (`generate_ulid()`).
* ULID gives you time‑ordered, globally unique IDs.
* It’s widely supported, boring and battle‑tested.

So:

> **Canonical format:**
> `"<prefix>_<payload>"`
> where `payload` is a standard 26‑char ULID (e.g. `01J4Q3D5G2Y4X5M2V5QBA4M0CD`).

If you prefer UUIDv7, same idea with 32‑char hex:

> `"<prefix>_<uuid7hex>"`

I’ll talk in terms of ULID, but everything below works almost identically for UUIDv7.

### 6.2 Prefix map

Your proposed prefixes are fine overall. I’d just ensure:

* Short (3–5 chars), consistent style.
* Reserve prefixes for user‑facing resources, not every tiny join table.

Example refinement:

* `usr_` — users
* `ws_` — workspaces
* `wsm_` — workspace memberships
* `role_`, `perm_`, `rperm_`, `princ_`, `rassign_` — RBAC tables
* `doc_`, `doctag_` — documents & tags
* `cfg_` — configurations
* `apk_` — API keys
* `sys_` — system settings
* `run_` — runs
* `bld_` — builds (shorter than `build_`, but either is fine)

I’d consider **not bothering** to prefix some purely internal join tables; you can keep them as ULIDs without prefixes inside the DB and never expose them.

### 6.3 Generator and validators

In `shared/core/ids.py`:

* Replace scattered `generate_ulid()` usages with:

  ```python
  def generate_id(prefix: str) -> str:
      payload = generate_ulid()  # or uuid7() in hex
      return f"{prefix}_{payload}"
  ```

* Centralize prefix knowledge in a map:

  ```python
  ResourcePrefix = Literal[
      "usr", "ws", "wsm", "role", "perm", "rperm", "princ",
      "rassign", "doc", "doctag", "cfg", "apk", "sys", "run", "bld"
  ]

  VALID_PREFIXES: set[str] = {...}
  ```

* Provide a **lenient** validator:

  ```python
  def is_valid_id(value: str) -> bool:
      # 1. Accept legacy bare ULIDs (26 chars) or legacy run/build UUID4 hex
      # 2. Accept <prefix>_<ULID>
      # Use regex but allow both for the foreseeable future
  ```

* TS side: mirror this with a small helper and type guards (`isWorkspaceId`, etc.).

### 6.4 DB schema

* **PK/FK column type:**
  Set all ID columns that will use prefixes to `String(40)`:

  * max prefix length 8 + underscore 1 + ULID 26 = 35
  * 40 leaves a bit of headroom.

* Update:

  * `ULIDPrimaryKeyMixin` to `String(40)` and to default to `generate_id(prefix)` where prefix is provided by model.
  * Any explicit `String(26)` / `String(40)` on FK columns → `String(40)`.

* For run/build, where columns are already `String(40)`, you’re already safe; you just change the generator.

### 6.5 How models get their prefix

Rather than letting each caller manually pass a prefix string, make it **part of the model definition**:

```python
class PrefixAwareIDMixin:
    id_prefix: ClassVar[str]

    id = Column(
        String(40),
        primary_key=True,
        default=lambda cls=Self: generate_id(cls.id_prefix)
    )
```

Then in each model:

```python
class Workspace(Base, PrefixAwareIDMixin):
    id_prefix = "ws"
    ...
```

This:

* Prevents inconsistencies in prefix usage.
* Keeps ID generation truly centralized.
* Makes it trivial to add tests “every model has a valid prefix”.

### 6.6 Cross‑layer usage (API, engine, CLI, storage)

Because the ID is just a string, your cross‑layer story barely changes:

* **API schemas / Pydantic / TS types**:

  * Document that IDs are “opaque, but typically look like `ws_<ulid>`”.
  * Use regex validation only where it’s helpful, but leave room to accept legacy values (e.g. union of patterns).

* **Storage layout**:

  * Directories under `./data/workspaces/<workspace_id>/...` can happily use `ws_<ulid>`.
  * No need for special shims, as long as code treats IDs as opaque.

* **Engine & CLI**:

  * Use the same generator and validator helpers.
  * Allow users to paste both old and new IDs for a while.

### 6.7 Migration strategy

Two scenarios:

#### A. No production DBs yet (or okay to reset them)

Do the clean sweep:

1. Update `0001_initial_schema.py` to:

   * Bump ID columns & FKs to `String(40)`.
   * Default PKs to `generate_id(<prefix>)`.
2. Remove `generate_ulid()` from anywhere except inside `generate_id`.
3. Standardize run/build IDs to `run_<ulid>` / `bld_<ulid>`.
4. Regenerate OpenAPI types, update fixtures, adjust tests.

You start the world with **only** prefixed ULIDs. No mixed formats long term.

#### B. There *is* existing data or integrations

Do an additive rollout:

1. **Schema changes first**:

   * Widen all relevant columns to `String(40)`.
2. **Roll out new generator**:

   * New rows get prefixed ULIDs.
   * Old rows keep bare ULIDs or `run_<uuid4hex>` etc.
3. **Update validators**:

   * Accept legacy bare ULIDs + new prefixed ULIDs for all affected endpoints.
4. **Touch storage only when needed**:

   * New runs/builds/workspaces store data under new IDs.
   * Old paths remain; you handle both in code if you care.

There is **no backfill**, no ID rewriting. Over time, old-style IDs become rare but remain valid.

---

## 7. Answering your open questions explicitly

> **Allow mixed legacy formats during transition?**

Yes. Architecturally, **plan to accept mixed formats indefinitely**.

> **Column length standard: String(60) vs tighter?**

Use **`String(40)`** (or `50` if you want lots of slack). 60 is unnecessary.

> **Uppercase vs lowercase hex?**

* For ULID: stick to the canonical base32 alphabet; case often irrelevant, but choose one (often upper).
* For UUIDv7 hex: **lowercase only** is what most people standardize on; validate case‑insensitively but output lower.

> **External integrations expecting bare ULIDs?**

Add a **compatibility layer** if needed:

* If an integration expects bare ULIDs, you can often:

  * Strip the prefix before sending (because payload is still a ULID), or
  * Introduce a dedicated field in the payload with the bare ULID.

> **Workspace/config routes & API**:

Your plan is sensible:

* Backends should accept both legacy and prefixed IDs for routes for a long time.
* You can move towards **slugs for user‑facing URLs** (`/workspaces/<slug>`), and use IDs mainly in API/CLI/programmatic contexts.

---

## 8. TL;DR: what I’d do for ADE

If I had to pick one path as “most standard, least painful” for you:

1. **Standardize on ULID + prefixes**:

   * `"<prefix>_<ulid>"`, with 26‑char ULID payload.
2. **Set all PK/FK ID columns to `String(40)`**.
3. **Centralize generation** in `shared/core/ids.py` with a single `generate_id(prefix)` entrypoint.
4. **Model‑level prefixes** via a mixin so you can’t get it wrong per table.
5. **Accept mixed formats** (legacy + new) everywhere in APIs and storage, and never rewrite existing IDs.
6. Optionally, in the future, you can introduce a decoupled `public_id` vs internal `id` if you start to regret coupling IDs so tightly across DB/API/storage.

This gets you:

* OpenAI‑like “resource‑type prefixes”,
* Time‑ordered, debuggable IDs,
* A generator pattern that is idiomatic and boring (ULID),
* Minimal schema and migration pain,
* A design that looks very normal to anyone joining the project later.

If you’d like, next step I can sketch the exact changes to:

* `ids.py`,
* the ORM mixins,
* and a few Pydantic/TS validators,

so you have a concrete, implementable plan.
