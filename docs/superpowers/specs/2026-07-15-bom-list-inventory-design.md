# Saved BOM lists on the inventory catalog

**Date:** 2026-07-15
**Status:** Implemented and verified — commit `35c2aeb`. Classification SQL (§6) executed.
**Branch:** v1

## Context

`GET /api/bom-lists` returns 500 in the live dev environment:

```
psycopg2.errors.UndefinedColumn: column bom_list_items.bom_id does not exist
```

### Root cause

The live PostgreSQL schema and the ORM disagree about what a BOM list item is.

| | `list_id` | item FK | `quantity` |
|---|---|---|---|
| **ORM** (`app/models.py:648`) | ✓ | `bom_id` → `bom_and_costing.id` | — |
| **Live `pjtrk.bom_list_items`** | ✓ | `inventory_id` → **`inventory.id`** | ✓ |

`Base.metadata.create_all()` only creates *missing tables* — it never alters an existing one. So the app booted with a stale mapping and failed only at query time.

The failure surfaces on **Saved Lists** specifically because `BomList.items` is `lazy="selectin"` (`models.py:630`): listing lists triggers an automatic second SELECT for items, which emits the non-existent `bom_list_items.bom_id`. The traceback's `strategies.py::_load_for_path` selectin-loader frame confirms this.

### How the drift arose

The `inventory` table (42 rows, all sharing a `2026-07-15 00:09:26` timestamp — a bulk load) and the rebuilt `bom_list_items` exist **only in the live database**. Nothing in the repo, git history, or any plan file references an `inventory` table; every "inventory" hit in the codebase is the *label* "BOM Inventory" for the `/bom` page (`parseBomInventoryExcel`, `BOM_INVENTORY_COLUMNS`).

The current `create_bom_list()` writes `BomListItem(bom_id=...)`, which cannot have produced the 113 `inventory_id` rows. The DB layer was hand-built ahead of the code — the same pattern as the earlier `category_id`/`type_id` work.

**This is a code-catches-up-to-data change.** The live schema is already the target. There is no ALTER to run and no migration of the existing 20 lists / 113 items.

### Live data inventory (verified read-only, 2026-07-15)

- `inventory`: 42 rows; `unit_price` fully populated; `category_id`, `type_id`, `lead_time` **NULL on all 42**; 11 distinct suppliers.
- `bom_lists`: 20 rows. `bom_list_items`: 113 rows across 19 lists (one list is empty). **No orphan references.**
- Quantities are real, hand-entered data — not a bulk default: qty 1 → 50 rows, qty 2 → 20, qty 3 → 24, qty 4 → 13, qty 6 → 6.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Adopt the inventory model in code** | The DB is intentional and holds 113 rows of deliberate data. Reverting is destructive and not symmetric — `inventory_id` values do not map back to `bom_and_costing` ids. |
| 2 | **`inventory` = reusable price book; `bom_and_costing` stays** | `/bom` and the per-project BOM are unchanged. `BomListPicker`'s source pool switches from BOM rows to catalog items. |
| 3 | **Catalog is read-only in the API** | `GET /api/inventory` only. Managed via SQL/seed for now. A CRUD UI is deferred to its own spec. |
| 4 | **Inline qty input per row** | Smallest change to the picker: the Qty column already exists and becomes editable. Default 1; Total renders live as `qty × unitPrice`. |
| 5 | **Auto-classify only unambiguous catalog rows** | 18 of 42 map confidently from `device_name` (verified by dry run); the other 24 stay NULL rather than be mislabelled by guesswork. |
| 6 | **Read-only verification against live Postgres** | The write path is verified on SQLite only. See *Known gaps*. |

### Why `inventory` is a separate resource (rejected alternative)

An alternative was to have `GET /api/inventory` pad rows into the existing BOM-row shape (`projectName: null`, `position: null`) so the picker and exports barely changed. Rejected: it bakes permanently-null fields into the contract and would leave the picker's "Filter by source project" filtering a column that cannot have values. A mapping that claims something the data does not support is precisely what caused this bug.

## Design

### 1. Data model — `app/models.py`

New `Inventory` model mapping the live table. It reuses `BomAndCosting`'s taxonomy-resolution pattern exactly (`category_ref` / `type_ref`, `lazy="joined"`, label falling back `description → name`):

```python
class Inventory(Base):
    __tablename__ = "inventory"

    id          = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("lookup_type.lookup_type_id"))
    type_id     = Column(Integer, ForeignKey("lookup_value.lookup_value_id"))
    device_name = Column(Text)
    version     = Column(Text)
    spec        = Column(Text)
    unit        = Column(Text)
    unit_price  = Column(Integer)
    supplier    = Column(Text)
    lead_time   = Column(Integer)
    created_at  = Column(DateTime, default=func.now())
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())

    category_ref = relationship("LookupType",  lazy="joined")
    type_ref     = relationship("LookupValue", lazy="joined")
```

`to_dict()` → `id, categoryId, category, typeId, type, deviceName, version, spec, unit, unitPrice, supplier, leadTime`.

It deliberately has **no** `projectId`, `position`, `quantity`, or `totalPrice` — that separation is the point of the model.

`BomListItem` is remapped to the real table; the `bom_id` column and `bom` relationship are **removed**:

```python
class BomListItem(Base):
    __tablename__ = "bom_list_items"

    list_id      = Column(Integer, ForeignKey("bom_lists.id", ondelete="CASCADE"), primary_key=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id", ondelete="CASCADE"), primary_key=True)
    quantity     = Column(Integer)

    parent    = relationship("BomList", back_populates="items")
    inventory = relationship("Inventory", lazy="joined")
```

`BomList.items` keeps `lazy="selectin"` — it is not the bug, it only surfaced it.

### 2. Catalog API — `app/api/inventory.py` (new)

- `GET /api/inventory` → `{"items": [...]}`, `@jwt_required()`, ordered by `device_name`.
- No POST/PATCH/DELETE (decision 3).
- Registered in `app/__init__.py` alongside the other blueprints.

### 3. List API — `app/api/bom_lists.py`

**Contract change.** Request body moves from `itemIds: [1, 2]` to:

```json
{ "name": "...", "projectId": 3, "items": [{ "inventoryId": 25, "quantity": 2 }] }
```

Quantity must ride per-item; parallel arrays would be fragile.

- `_validate_item_ids` → `_validate_items`: `inventoryId` required int; `quantity` optional int defaulting to **1**, must be **≥ 1**; dedupe by `inventoryId` (the composite PK forbids repeats — last quantity wins).
- `_ensure_boms_exist` → `_ensure_inventory_exists` (422 listing unknown ids).
- `_replace_items` constructs `BomListItem(inventory_id=..., quantity=...)`.
- `_serialize_detail` **drops the source-project bulk lookup entirely** (a catalog item has no project) and emits per item:
  `{**inventory.to_dict(), "quantity": qty, "totalPrice": qty * unitPrice}`.
  **`totalPrice` is computed, never stored.** `unitPrice` is non-null on all 42 rows today; treat a null `unitPrice` as a null `totalPrice` rather than raising.
- The module docstring's "Cross-project items are allowed" premise is now obsolete and must be rewritten — a list is target-project-scoped, and its items are project-independent catalog entries.

Authz is unchanged: read for any authenticated user, owner-or-admin on PATCH/DELETE.

### 4. Frontend

| File | Change |
|---|---|
| `stores/inventory.js` (new) | Mirrors `stores/bom.js`: `rows`, `loading`, `fetchAll()`. The `bom` store is untouched and still serves `/bom`. |
| `api/index.js` | Add `listInventory()`. |
| `components/BomListsManager.vue` | No functional change — `doExport` passes `detail.items` straight through to the export helpers. **But its line-40 comment ("Detail endpoint enriches each item with projectName already") becomes false** and must be corrected, since `projectName` is being removed from items. |
| `components/BomListPicker.vue` | Pool ← inventory store. Selection becomes `Map<inventoryId, quantity>` (was `Set<id>`). **Remove** "Filter by source project" + Project column, and Position filter + column — neither exists on a catalog item. **Qty** becomes a `number` input (min 1, default 1, enabled when ticked). **Total price** renders live as `qty × unitPrice`. Category/Type filters *simplify*: inventory has real FK ids and no free-text `category` column, so the `categoryMatchSet`/`typeMatchSet` free-text fallbacks are deleted and matching is a direct id compare. `COL_COUNT` and `DEVICE_COL` shift accordingly. |
| `utils/recordExport.js` | BOM-list Excel/PDF column set drops Project and Position; Total = `qty × unitPrice`. |
| `views/BomGlobalView.vue` | `/bom` itself unchanged. Only the `request-pdf-export` row shape changes, absorbed by `recordExport`. |

`BomExportDocsModal` and the PDF document-attachment flow are **untouched** — they key off the list's *target* project, which still exists.

#### ⚠ Edit-mode must round-trip quantities (data-loss risk)

`save()` always resends the **full** selection, and the backend `_replace_items` **clears and rebuilds every row**. So the edit-mode seed is load-bearing. Today it is (`BomListPicker.vue:294`):

```js
selectedIds.value = new Set((detail.items || []).map((it) => it.id))
```

If that becomes a `Set`, or a `Map` that defaults quantity to 1, then **a user who opens an existing list merely to rename it and hits Save silently overwrites every quantity with 1** — destroying the 63 hand-entered qty 2/3/4/6 rows this migration exists to preserve.

**Requirement:** edit mode MUST seed quantity from the detail payload, and save MUST round-trip it unchanged:

```js
selected.value = new Map((detail.items || []).map((it) => [it.id, it.quantity ?? 1]))
```

This is guarded by a mandatory round-trip test (below). The read-only Postgres verification **cannot** catch this, because it never saves.

### 5. DDL mirror — `backend/init_db.sql`

Add the `inventory` DDL and update `bom_list_items` to `(list_id, inventory_id, quantity)` with `PRIMARY KEY (list_id, inventory_id)`. Documentation-only for the live DB (which already matches), but it is what makes a fresh install correct.

### 6. Catalog classification (one-time, run separately)

> **STATUS: executed 2026-07-15** against live `pjtrk` with user approval — 18 rows classified, 24 left NULL, list data verified untouched (quantity histogram unchanged). Re-runnable but now a no-op for those 18 (`WHERE category_id IS NULL`).

Populates `category_id` on unambiguous rows only.

```sql
-- One-time classification of unambiguous inventory rows.
-- Only rows whose device_name explicitly names its device class are touched;
-- everything else stays NULL and simply won't match a Category filter.
UPDATE pjtrk.inventory AS i
SET    category_id = t.lookup_type_id
FROM   pjtrk.lookup_type AS t
WHERE  i.category_id IS NULL
  AND  t.code = CASE
         WHEN i.device_name ILIKE 'Industrial Camera :%' THEN 'CAMERA'
         WHEN i.device_name ILIKE 'Cable :%'             THEN 'CABLE'
         WHEN i.device_name ILIKE 'Lens :%'              THEN 'LENS'
         WHEN i.device_name ILIKE 'Lighting :%'          THEN 'LIGHTING'
         WHEN i.device_name ILIKE 'Indutrial PC :%'
           OR i.device_name ILIKE 'Industrial PC :%'     THEN 'PC'
         WHEN i.device_name ILIKE 'PLC %'                THEN 'PLC'
         WHEN i.device_name ILIKE 'Switch Cisco%'        THEN 'ETHERNET_SWITCH'
         WHEN i.device_name ILIKE 'Server %'             THEN 'SERVER'
         WHEN i.device_name ILIKE 'Firewall %'           THEN 'FIREWALL'
         WHEN i.device_name ILIKE 'UPS %'                THEN 'UPS'
       END;
```

**Verified by read-only dry run against the live DB (2026-07-15): exactly 18 rows updated, 24 left NULL, and every mapped code exists in `lookup_type`** (so no row silently drops through the join). Breakdown: Camera ×3 (ids 1, 2, 39), Cable ×3 (3, 4, 12), Lens ×3 (5, 6, 38), Lighting ×3 (7, 8, 40), PC ×1 (11), PLC ×1 (13), Ethernet switch ×1 (14), Server ×1 (15), Firewall ×1 (16), UPS ×1 (19). `type_id` stays NULL throughout.

`'Indutrial PC :%'` matches the existing typo in the live data; both spellings are handled. `'Lighting :%'` is anchored, so `Control Lighting : 4 Channels` (a controller, not a light) is correctly **not** matched.

**Deliberately left NULL** (24 rows): bare model numbers needing domain knowledge (`LJ-S8000`, `SI410`, `SR-x100`, `MATRIX-320`, `VX4-UMNA-A1C`, `OP-01`, `FX5U-32MT/DS`), one-offs (`Wiring`, `Electric&Network`, `HMI`, `OPT-IPC`, `Load cell HSX-A`, `ตู้ Control`, `Cover Camera S.1/2/4`, `19"GERMAN CABINET RACK`, `CX-RT Labeling Machine`, `W37N OverWrap`), and rows with **no matching `lookup_type` at all** (`Vision Software` ids 10 & 42 — the two most expensive IIS items; the labelling machines).

#### Optional follow-up (needs separate approval)

Several `type_id` values look confidently derivable: `Industrial Camera :%` → `INDUSTRIAL_CAM`; `Lens : … C-mount` → `CMOUNT`; `Lighting : Bar Light` → Bar-light; `Indutrial PC : … i7` → `I7`; `PLC … IQ-R` → `IQR`; `Cable : USB3.0` → `COM`; `Cable : Power I/O` → `IO_POWER`.

#### Pre-existing taxonomy data issues (observed, not fixed here)

- `lookup_value` code `ฺBAR` (LIGHTING → Bar-light) carries a **stray Thai combining character** (U+0E3A) — this would break any code-based matching.
- `ETHERNET_SWITCH` holds values "Display/Monitoring" and "HMI screen"; `SERVER` holds a lone "Firewall" value. These appear misfiled.
- `ACCESSORY`, `ETC`, and `MONITOR_SCREEN` have zero `lookup_value` children.
- No `lookup_type` exists for software or machines.

## Verification

**pytest is NOT pointed at live Postgres.** The suite creates and deletes rows and `seed.py` drops the schema; aiming it at `pjtrk` would destroy the 20 lists / 113 items / 124 BOM rows this migration exists to preserve.

### a. Schema-vs-ORM drift check (read-only)

Reflect `pjtrk.bom_list_items` and `pjtrk.inventory` from the live DB and assert every ORM column exists with matching name and type. **This is the check that would have caught this bug at startup instead of at click time.**

### b. Replay the failing query (read-only)

Execute the exact `list_bom_lists()` path against live data — the `BomList`/`Project` outerjoin **plus** the `selectin` load of `items` that actually threw. Assert 20 lists load and 113 items resolve with no exception. Direct regression proof for the reported 500.

### c. End-to-end through the running app (read-only)

Restart Flask manually — **it does not auto-reload** (`FLASK_DEBUG=false`). Then against live Postgres:

1. `GET /api/bom-lists` → 200; 20 lists; `itemCount` matches the DB.
2. `GET /api/bom-lists/<id>` → `items[]` carry `quantity`, checked specifically against the **qty 2/3/4/6** rows (not only the 50 rows at qty 1), and `totalPrice == quantity × unitPrice`.
3. `GET /api/inventory` → 42 rows.
4. **Browser: `/bom` → Saved Lists renders the 19 non-empty lists with no 500.** Open the picker; confirm catalog rows and working qty inputs.

**Step 4 is the acceptance criterion** — it is the exact action that produced the report.

### d. SQLite suite (fast logic guard)

`cd backend && .venv/Scripts/python -m pytest tests/ -v`

- `test_bom_lists.py`: fixtures insert `Inventory` via `Session.add()` (the catalog has no POST endpoint). Rewrite `itemIds` → `items`. Cover quantity defaulting to 1, quantity < 1 → 422, unknown `inventoryId` → 422, duplicate ids deduped, `totalPrice` math, and the existing cascade tests re-pointed at `inventory`.
- **`test_bom_lists.py::test_patch_preserves_item_quantities` (mandatory).** Create a list with mixed quantities (e.g. 1/2/6), `PATCH` **only** the `name`, then re-fetch and assert every per-item quantity is unchanged (this pins the `if "items" in data` guard — an absent `items` key must never touch rows). Then re-send the same `items` payload and assert quantities still survive the `_replace_items` clear-and-rebuild.

  **What this does *not* cover:** it proves the API preserves what it is *sent*. The actual data-loss path is the **frontend** seeding `quantity: 1` and faithfully sending it — which the backend would then correctly honour. See *Known gaps*.
- `test_inventory.py` (new): `GET /api/inventory` authz + payload shape.

## Known gaps (accepted)

- **The edit-mode quantity seed has no automated *regression* guard.** The project has **no frontend test framework** (no vitest/test script in `frontend/package.json`), so the `BomListPicker` seed — the one line that could reset 63 quantities to 1 — has no test standing behind it. The backend round-trip test cannot cover it (the API would be faithfully honouring a wrong payload).
  **Verified once, manually (2026-07-15, read-only):** opened list 10 (`ทดสอบยาสูบ`, 12 items) in edit mode against live Postgres; the qty inputs seeded to `[6,6,3,3,3,3,3,3,2,1,1,1]` — the stored values, not 1s — then cancelled without saving. Re-check this by hand if the seed or `save()` is ever touched.

- **Postgres write-path behaviour is unverified** by automation. Composite-PK conflict handling and `ON DELETE CASCADE` differ between SQLite and Postgres; per decision 6 verification is read-only, so the first real save exercises this. Automated Postgres coverage would need a **disposable** database (throwaway schema or container) — its own scope.
- **`search_path=pjtrk` resolution is untested** by the suite (SQLite-only) — though the live end-to-end verification below did exercise it. Already flagged in the Render/Supabase plan.
- **Category filters match only 18 of 42 catalog rows, and Type matches none.** Classification ran (§6); the remaining 24 need domain knowledge. Consistent with the "lights up as rows are reclassified" stance accepted for Type in the earlier lookup-taxonomy work.

## Non-goals

- Inventory CRUD UI (deferred to its own spec).
- Changes to `/bom`, `bom_and_costing`, or the BOM Excel import.
- Fixing the pre-existing taxonomy data issues listed above.
- Materializing saved lists into `bom_and_costing` rows.

## Files touched

**Backend:** `app/models.py`, `app/api/inventory.py` (new), `app/api/bom_lists.py`, `app/__init__.py`, `init_db.sql`, `tests/test_bom_lists.py`, `tests/test_inventory.py` (new)

**Frontend:** `src/stores/inventory.js` (new), `src/api/index.js`, `src/components/BomListPicker.vue`, `src/components/BomListsManager.vue` (stale comment only), `src/utils/recordExport.js`

**Docs:** `CLAUDE.md` (records API table + Key Decisions), this spec
