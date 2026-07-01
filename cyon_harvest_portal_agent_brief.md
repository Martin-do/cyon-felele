# CYON Harvest Portal — Agent Brief

Project: Django church-fundraising platform (`cgscc_cyon`). Apps: `accounts`, `contributions`, `dashboard`, `live`, project config in `config/`.

Read `ORIGINAL_REQUEST.md` and `progress.md` in the repo root first — they're the existing changelog/spec from prior agent sessions.

---

## 1. Codebase map (so you don't need to re-explore)

**Routing**: `config/urls.py` includes each app's `urls.py`. Each `path()` line maps directly to a function in that app's `views.py` — start there, not by grepping.

- `contributions/` (public, no login)
  - `/` → `landing_page_view` → `landing.html`
  - `/support/<slug>/` → `donation_form_view` → `donation_form.html`
  - `/api/contribute/` → `ContributionCreateAPIView` (DRF) — creates a `Contribution`
  - `/api/verify-paystack/` → `VerifyPaystackPaymentView`
  - `/api/names/search/` → `NameSearchAPIView`
  - `/receipt/<uuid>/` → `receipt_view`
  - Voting/contestant flow: `donation_form_view` also serves `contestant_vote.html` for `/support/<referral_slug>/` when the slug belongs to a contestant
- `accounts/`: `login_view`, `signup_view`, `onboarding_view`, `forgot_pin_view`, `settings_view`, `verify_pin_api`, `logout_view`
- `dashboard/` (largest file, ~1500 lines)
  - Member-facing: `member_hub_view`, `my_pledges_view`, `create_self_pledge_view`, `redeem_pledge_view`, `generate_flyer_view`/`public_flyer_view`, `generate_qr_code_view`, `leaderboard_view` (+ `get_leaderboard_standings_helper`)
  - Admin-facing: `master_dashboard_view` (page load) + `AdminTransactionListAPIView` (live AJAX data — **this is the one that actually drives the dashboard numbers**, not the page-load context), `export_csv_view`, `approval_center_view`, `approve_contribution_view`/`reject_contribution_view`, `update_member_role_view`, `add_inflow_category_view`, `import_parishioners_view`, `send_announcement_view`, `record_pledge_view`, `approve_pledge_view`, `revoke_pledge_view`, `ContributionActionAPIView`, `RequeryPaystackTransactionView`
  - Access control decorators: `admin_required`, `approver_required`, `usher_required`
- `live/`: `/live/board/` → `projector_board_view` → `board.html`, backed by `consumers.py` (Django Channels websocket)

**Models** (`contributions/models.py`, `accounts/models.py`): `Member` (custom auth user), `Contribution` (has `pledge` FK, `method` free-text field, `status`: pending/approved/rejected, `is_voided`), `Pledge` (`amount_pledged`, `amount_fulfilled`, `status`: pending/approved/voided, `inflow_category`), `Parishioner`, `InflowCategory`, `HarvestSession`.

---

## 2. Already fixed manually — do not redo, just be aware

1. **CSRF bug**: `contributions/templates/contributions/donation_form.html` and `contestant_vote.html` — the manual Cash/Transfer/Pledge submit to `/api/contribute/` was missing the `X-CSRFToken` header (the Paystack flow had it, manual didn't). `SessionAuthentication` is on globally in `config/settings.py`, so any logged-in session hit a 403. Both now send the header. ✅ done.

2. **Financial accounting rewrite** in `dashboard/views.py` (`AdminTransactionListAPIView.get()` and `master_dashboard_view`):
   - Bug found: `AdminTransactionListAPIView` had no default `status` filter, so on initial page load pending/rejected contributions were silently counted into "Total Raised" until an admin manually filtered. **Fixed**: headline stats are now always scoped to `status='approved'`, independent of whatever status the admin's table view is currently filtered to.
   - Business rule implemented (per product owner): a pledge's full `amount_pledged` counts toward Total Raised **once**, at approval — pulled from the `Pledge` model directly. When later redeemed, the resulting `Contribution` (linked via `pledge` FK) is **excluded** from Total Raised / Cash / Transfer / Online, and instead summed into a new **Pledge Redemptions** figure (audit-only, never re-added to the total).
   - `export_csv_view` now tags rows `Direct` vs `Pledge Redemption`, and appends a committed-pledges section for full audit trail.
   - Template `admin_master.html` got a new "Pledge Redemptions" stat card wired to `data.pledge_redemptions`.
   - **POS is intentionally not implemented** — no physical POS device exists; POS payments get recorded as Transfer.

---

## 3. Open items for you to handle

### 3a. Verify migrations on the real/deployed database
The `db.sqlite3` shipped with the project snapshot only had migrations through `contributions/0008` applied — `0009_inflowcategory_contribution_inflow_category_and_more.py` through `0012_contribution_pledge_pledge_member_pledge_status.py` (which create `InflowCategory` and `Pledge`) were **not applied**. This is the most likely cause of "Total Raised breakdown shows no data" on the member dashboard (`member_hub_view`'s `category_stats` loop depends on `InflowCategory` rows existing).

**Action**: run `python manage.py showmigrations contributions` on the actual deployed database. If `0009`–`0012` are unapplied, run `python manage.py migrate`. Confirm `InflowCategory.objects.filter(is_active=True)` returns rows afterward (migration `0011` seeds them).

### 3b. Voting-page leaderboard ranking — needs a product decision before you touch it
`donation_form_view`'s contestant ranking and `get_leaderboard_standings_helper` both compute totals correctly (sum of `Contribution.amount` where `referred_by=member, status='approved', is_voided=False`) — the math is not the bug. The likely cause of "inaccurate ranking" is that on the voting page, "Manual Transfer" submissions sit as `pending` until an admin approves them, while Paystack payments count instantly. So a contestant's live rank lags behind reality whenever supporters pay by manual transfer.

**Do not silently change this.** Two options, pick one:
- **Option A (status quo, hardened)**: keep ranking strictly `approved`-only — it's the "audited" number — but speed up admin approval turnaround (e.g. notification on new pending manual transfers) so the lag is shorter.
- **Option B**: show pending manual-transfer amounts on the leaderboard too, visually flagged (e.g. "(pending verification)"), so live standings reflect activity in real time while still being clearly distinguished from confirmed totals.

Ask the user which they want before implementing.

### 3c. Sanity-check after any further pledge/contribution changes
Whenever you touch `Contribution` or `Pledge` creation/approval logic, re-verify this invariant holds:
```
Total Raised == sum(approved Contribution.amount where pledge IS NULL) + sum(approved Pledge.amount_pledged)
```
and that `pledge_redemptions` (`sum(approved Contribution.amount where pledge IS NOT NULL)`) is never added into Total Raised. This is the audit-correctness rule the financial rewrite in §2 depends on — don't reintroduce double counting.

---

## 4. Constraints / house rules
- No POS payment method — don't add it back.
- `Contribution.method` is free text (no choices enforced) — when filtering, use `method__icontains` consistently with existing buckets (`Cash`, `Transfer`, `Pledge`, `Online`/`Paystack`).
- Guest-declared pledges via the public donation form (`method='Pledge'` Contribution, no `Pledge` row) and member-hub pledges (`Pledge` model with `amount_pledged`/`amount_fulfilled`) are two different mechanisms that both roll into the same "Pledges" stat bucket — don't conflate their underlying tables when writing queries.
