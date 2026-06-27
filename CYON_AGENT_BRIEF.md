# CYON Harvest Portal — Agent Fix Brief
> Verified against the live codebase (cgscc_cyon.zip) and the live debug endpoint output.
> Organised by priority. Do not skip Section 1 — those are active security holes.

---

## Context Summary

The portal is a parish harvest fundraising system where:
- Youth members register, get a unique referral link, and download a shareable flyer
- Visitors access a youth's link, see their position on the leaderboard, and vote by paying online (Paystack) or via manual transfer
- Ushers with the `usher` role record live/physical payments during church events
- Approvers with the `approver` role verify manual transfer contributions
- Admins manage the full dashboard

Four roles are already defined and all role-check decorators exist:
`member` → `usher` → `approver` → `admin`

---

## Section 1 — Critical Security Fixes

### 1.1 `add_inflow_category_view` has no auth decorator

**File:** `dashboard/views.py`

Anyone on the internet can POST to `/dashboard/master/categories/add/` and create or
spam inflow categories without logging in.

```python
# FIND (the function definition line):
def add_inflow_category_view(request):

# REPLACE WITH:
@admin_required
def add_inflow_category_view(request):
```

---

### 1.2 `approve_contribution_view` has no auth decorator

**File:** `dashboard/views.py`

Anyone can POST to `/dashboard/approve/<pk>/` to approve any contribution without
being authenticated or having the approver role.

```python
# FIND:
def approve_contribution_view(request, pk):

# REPLACE WITH:
@approver_required
def approve_contribution_view(request, pk):
```

---

### 1.3 Remove the debug endpoint

**File:** `dashboard/views.py` and `dashboard/urls.py`

The debug endpoint at `/dashboard/master/debug-members/` exposes every member's
name, identifier (email/phone), role, and access flags to any logged-in user.
It was useful for diagnosis but must be removed before the portal goes public.

**In `dashboard/views.py`** — delete the entire function:
```python
# DELETE this entire function:
@admin_required
def debug_members_view(request):
    """Temporary debug endpoint to diagnose member visibility issues."""
    ...
```

**In `dashboard/urls.py`** — delete the matching URL entry:
```python
# DELETE this line:
path('master/debug-members/', views.debug_members_view, name='debug_members'),
```

---

## Section 2 — Bug Fixes

### 2.1 OG image URL is relative — social media previews will not load

**File:** `contributions/views.py`, inside `donation_form_view`

Social media crawlers (WhatsApp, Twitter, Facebook) require an **absolute URL**
for `og:image`. The current code produces a relative path like `/media/flyers/1.png`
which crawlers cannot fetch.

Additionally, the `custom_flyer` field on Member (for user-uploaded flyers) is never
checked — the code only looks at the Playwright-generated file.

```python
# FIND (approximately — the og_image_url block near the end of the referral branch):
import os
flyer_path = os.path.join(settings.MEDIA_ROOT, 'flyers', f"{referrer.id}.png")
og_image_url = f"{settings.MEDIA_URL}flyers/{referrer.id}.png" if os.path.exists(flyer_path) else None

# REPLACE WITH:
import os
og_image_url = None
if referrer.custom_flyer:
    # User uploaded a custom flyer — use it first
    og_image_url = request.build_absolute_uri(referrer.custom_flyer.url)
else:
    # Fall back to Playwright-generated flyer
    flyer_path = os.path.join(settings.MEDIA_ROOT, 'flyers', f"{referrer.id}.png")
    if os.path.exists(flyer_path):
        og_image_url = request.build_absolute_uri(
            f"{settings.MEDIA_URL}flyers/{referrer.id}.png"
        )
```

---

### 2.2 Live entry has no double-submit protection

**File:** `dashboard/views.py` (`live_entry_view`) and `dashboard/templates/dashboard/live_entry.html`

The `Contribution` model already has an `idempotency_key` UUID field, and the
Paystack flow already uses `get_or_create` on it. But the live entry view uses a
bare `Contribution.objects.create()` — if an usher double-taps Submit, two identical
records are created.

**In the live entry template**, add a hidden field and auto-refresh it via JS:
```html
<!-- Add inside the live entry <form> tag -->
<input type="hidden" name="idempotency_key" id="idempotency_key_field">

<!-- Add in the <script> section of the same template -->
<script>
  function generateUUID() {
    return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
      (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  }
  // Set a fresh key on page load
  document.getElementById('idempotency_key_field').value = generateUUID();

  // Refresh the key after each successful submission so the next entry is clean
  document.querySelector('form').addEventListener('submit', function() {
    setTimeout(function() {
      document.getElementById('idempotency_key_field').value = generateUUID();
    }, 500);
  });
</script>
```

**In `dashboard/views.py`** (`live_entry_view`), replace the bare `create()`:
```python
# FIND (inside live_entry_view POST block):
Contribution.objects.create(
    name=name,
    amount=amount,
    method=method,
    phone=phone,
    referred_by=referrer,
    inflow_category=category,
    source='live_log',
    status='approved',
    recorder_id=request.user.name if request.user.name else request.user.identifier
)

# REPLACE WITH:
import uuid as uuid_module
idempotency_key = request.POST.get('idempotency_key', '').strip()
try:
    key = uuid_module.UUID(idempotency_key)
except (ValueError, AttributeError):
    key = uuid_module.uuid4()  # fallback if JS didn't fire

contribution, created = Contribution.objects.get_or_create(
    idempotency_key=key,
    defaults={
        'name': name,
        'amount': amount,
        'method': method,
        'phone': phone,
        'referred_by': referrer,
        'inflow_category': category,
        'source': 'live_log',
        'status': 'approved',
        'recorder_id': request.user.identifier,  # identifier is more stable than name
    }
)
if not created:
    messages.warning(request, "Duplicate submission detected — entry already recorded.")
    return redirect('dashboard:live_entry')
```

---

### 2.3 Leaderboard has an N+1 query problem

**File:** `contributions/views.py`, inside `donation_form_view`

The current code loops over all competitors and fires a separate DB query for each
one to get their total. With 20 contestants this is 21 queries; with 50 it is 51.

```python
# FIND (the leaderboard calculation block):
leaderboard = []
for comp in competitors:
    comp_total = Contribution.objects.filter(referred_by=comp, is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
    leaderboard.append({'id': comp.id, 'total': comp_total})
    if comp.id == referrer.id:
        total_amount = comp_total

leaderboard = sorted(leaderboard, key=lambda x: x['total'], reverse=True)

top_3 = []
for index, item in enumerate(leaderboard):
    if index < 3:
        comp_member = Member.objects.get(id=item['id'])
        top_3.append({ ... })
    if item['id'] == referrer.id:
        leaderboard_position = index + 1

# REPLACE WITH (2 queries total, regardless of contestant count):
from django.db.models import Sum, Q

competitors = (
    Member.objects
    .filter(is_active=True, is_staff=False, contestant_title=referrer.contestant_title)
    .annotate(
        total_raised=Sum(
            'referrals__amount',
            filter=Q(referrals__is_voided=False, referrals__status='approved')
        )
    )
    .order_by('-total_raised')
)

top_3 = []
leaderboard_position = None
total_amount = 0

for index, comp in enumerate(competitors):
    comp_total = comp.total_raised or 0.00
    rank = index + 1

    if index < 3:
        top_3.append({
            'rank': rank,
            'name': comp.name,
            'total': comp_total,
            'votes': int(comp_total // 500),
            'picture_url': comp.profile_picture.url if comp.profile_picture else None,
            'initial': comp.name[0].upper(),
        })

    if comp.id == referrer.id:
        leaderboard_position = rank
        total_amount = comp_total
```

---

### 2.4 `recorder_id` stores usher name (unstable) instead of identifier

**File:** `dashboard/views.py`, inside `live_entry_view`

Names can be changed on the settings page. Storing the identifier (phone/email) means
records always trace back to the right account even after a name change. This is a
one-character fix.

```python
# FIND:
recorder_id=request.user.name if request.user.name else request.user.identifier

# REPLACE WITH:
recorder_id=request.user.identifier
```

---

## Section 3 — Feature Completions

### 3.1 Add Edit and Deactivate actions for Inflow Categories

**Context:** The Inflow Categories tab already has an "Add New Category" form.
But once a category is created, there is no way to rename it or deactivate it
from the frontend — the admin must use `/admin/` (which also requires registering
the model there; see 3.2).

**Add two new views to `dashboard/views.py`:**

```python
@admin_required
def edit_inflow_category_view(request, pk):
    category = get_object_or_404(InflowCategory, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            category.name = name
            category.description = description
            category.save()
            messages.success(request, f"Category updated to '{name}'.")
        else:
            messages.error(request, "Category name is required.")
    return redirect('dashboard:master_dashboard')


@admin_required
def toggle_inflow_category_view(request, pk):
    category = get_object_or_404(InflowCategory, pk=pk)
    if request.method == 'POST':
        category.is_active = not category.is_active
        category.save()
        state = "activated" if category.is_active else "deactivated"
        messages.success(request, f"Category '{category.name}' {state}.")
    return redirect('dashboard:master_dashboard')
```

**Add to `dashboard/urls.py`:**
```python
path('master/categories/<int:pk>/edit/', views.edit_inflow_category_view, name='edit_inflow_category'),
path('master/categories/<int:pk>/toggle/', views.toggle_inflow_category_view, name='toggle_inflow_category'),
```

**In the Inflow Categories tab of `admin_master.html`**, add Edit and Toggle buttons
next to each category in the list, similar to how the PIN reset table has action buttons.

---

### 3.2 Register `InflowCategory` in Django admin

**File:** `contributions/admin.py`

The model is not registered, so it cannot be managed from `/admin/` at all.

```python
# ADD to the imports at the top:
from .models import Contribution, Pledge, HarvestSession, Parishioner, InflowCategory

# ADD this class anywhere in the file:
@admin.register(InflowCategory)
class InflowCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'api_key_name', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
```

---

### 3.3 Add a Parishioner bulk-import view

**Context:** The `Parishioner` model exists and the `NameSearchAPIView` autocomplete
is wired to it — but the table is empty on the live server. Without data, the usher's
name-search autocomplete during live entry will show nothing.

The admin needs a way to paste or upload a list of parish member names.

**Add to `dashboard/views.py`:**
```python
@admin_required
def import_parishioners_view(request):
    if request.method == 'POST':
        raw = request.POST.get('names', '')
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        created, skipped = 0, 0
        for name in lines:
            _, was_created = Parishioner.objects.get_or_create(
                name__iexact=name,
                defaults={'name': name, 'source': 'registry'}
            )
            if was_created:
                created += 1
            else:
                skipped += 1
        messages.success(request, f"Import complete: {created} added, {skipped} already existed.")
    return redirect('dashboard:master_dashboard')
```

**Add to `dashboard/urls.py`:**
```python
path('master/parishioners/import/', views.import_parishioners_view, name='import_parishioners'),
```

**Add a simple textarea form to the master dashboard** (can be a new tab or a section
inside the existing layout):
```html
<form method="POST" action="{% url 'dashboard:import_parishioners' %}">
    {% csrf_token %}
    <label>Paste parish member names (one per line):</label>
    <textarea name="names" rows="10" placeholder="Adeyemi Blessing&#10;Okafor Emmanuel&#10;..."></textarea>
    <button type="submit">Import Names</button>
</form>
```

---

### 3.4 Replace the receipt notification placeholder

**File:** `dashboard/views.py`, inside `approve_contribution_view`

The current code only prints to the server log:
```python
print(f"NOTIFICATION: Sending approval notice to {contribution.name} at {contribution.phone}.")
```

The portal already has a WhatsApp gateway (Baileys microservice used by SHCSS).
Replace the `print()` with a real POST to that gateway:

```python
# REPLACE the print() line with:
import requests as http_requests
receipt_url = request.build_absolute_uri(
    reverse('contributions:receipt', args=[str(contribution.id)])
)
try:
    phone = contribution.phone
    if phone and not phone.startswith('+'):
        # Normalise Nigerian numbers
        phone = '234' + phone.lstrip('0')
    if phone:
        http_requests.post(
            'http://localhost:3000/send',   # adjust to your Baileys service port
            json={
                'phone': phone,
                'message': (
                    f"✅ Hello {contribution.name}, your contribution of "
                    f"₦{contribution.amount:,.0f} to the CYON Harvest has been confirmed!\n\n"
                    f"View your receipt here: {receipt_url}\n\n"
                    "Thank you for supporting our youth. 🙏"
                )
            },
            timeout=5
        )
except Exception:
    pass  # Never let a notification failure block the approval response
```

---

## Section 4 — Admin Actions (no code required)

These require the admin to take manual action on the live server.

### 4.1 Create Inflow Categories

The form already exists on the **Inflow Categories tab** of the master dashboard.
Log in as admin, click that tab, and create the categories relevant to the harvest
campaign, for example:
- Main Harvest Contributions
- Pledge Redemptions
- Youth Week Fundraiser
- Online / Paystack

### 4.2 Load Parishioner Names

After deploying Section 3.3, go to the master dashboard and paste the church register
names (one per line) into the import form. This populates the autocomplete that ushers
use during live entry to quickly find parishioner names.

### 4.3 Fix the admin account name

The admin account (id=2) has a stray tab character in its name: `"admin\t"`.
Go to `/admin/accounts/member/2/change/` and correct the name to the proper
display name (e.g. `CYON Admin` or your real name).

---

## Summary Table

| # | File(s) | Type | Effort |
|---|---------|------|--------|
| 1.1 | `dashboard/views.py` | 🔴 Security | 1 line |
| 1.2 | `dashboard/views.py` | 🔴 Security | 1 line |
| 1.3 | `dashboard/views.py` + `urls.py` | 🔴 Security | Delete ~15 lines |
| 2.1 | `contributions/views.py` | 🟡 Bug | ~8 lines |
| 2.2 | `dashboard/views.py` + live_entry template | 🟡 Bug | ~25 lines |
| 2.3 | `contributions/views.py` | 🟡 Performance | ~20 lines |
| 2.4 | `dashboard/views.py` | 🟡 Bug | 1 line |
| 3.1 | `dashboard/views.py` + `urls.py` + template | 🔵 Feature | ~30 lines |
| 3.2 | `contributions/admin.py` | 🔵 Feature | ~8 lines |
| 3.3 | `dashboard/views.py` + `urls.py` + template | 🔵 Feature | ~30 lines |
| 3.4 | `dashboard/views.py` | 🔵 Feature | ~20 lines |
| 4.x | Admin panel / dashboard UI | 🟢 Admin task | No code |

**No model changes and no migrations are required for any of the above.**
