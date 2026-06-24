# CYON Ambassador Flyer Generator — Agent Implementation Guide

Dynamic flyer generation for the CYON Digital Harvest Portal. Given a contestant's
name, photo, category, and voting URL, the system renders a 1080×1080 PNG flyer
by screenshotting a Jinja2/Django HTML template with Playwright (headless Chromium).

---

## 1. Dependencies

```bash
pip install playwright qrcode[pil] Pillow rembg
playwright install chromium
```

> **rembg** is optional but strongly recommended — it removes the photo background
> so the contestant portrait blends cleanly into the blue card (like the original
> flyer design). Install it separately if it causes conflicts:
> ```bash
> pip install rembg onnxruntime
> ```

---

## 2. File Structure

Place files exactly as shown relative to your Django project root:

```
your_project/
├── harvest/                        ← your Django app
│   ├── flyer_generator.py          ← utility (Section 4)
│   ├── urls.py                     ← add flyer_view route (Section 5)
│   └── models.py                   ← see Contestant model hint (Section 6)
├── templates/
│   └── flyers/
│       └── ambassador_flyer.html   ← Jinja2 template (Section 3)
├── static/
│   └── images/
│       └── church_logo.png         ← church/CYON logo static asset
└── media/
    └── flyers/                     ← auto-created; cached PNG output lives here
```

---

## 3. HTML Template

Save as `templates/flyers/ambassador_flyer.html`.

**Jinja2 variables this template expects:**

| Variable         | Example value                                              |
|------------------|------------------------------------------------------------|
| `{{ logo_url }}` | `https://yoursite.com/static/images/church_logo.png`       |
| `{{ photo_url }}`| Absolute URL or base64 data URI of contestant photo        |
| `{{ name }}`     | `MARTIN JAIYEOLA` (auto-uppercased in Python before render)|
| `{{ category }}` | `Youth Category (Male): Most Influential Youth Fundraiser` |
| `{{ vote_url }}` | `https://harvest.cyon.ng/vote/42`                          |
| `{{ contact_phone }}` | `09134156737`                                         |
| `{{ qr_url }}`   | Base64 data URI — auto-generated in Python from `vote_url` |

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    *, *::before, *::after {
      margin: 0; padding: 0; box-sizing: border-box;
    }

    body {
      width: 1080px;
      height: 1080px;
      background: #ffffff;
      font-family: 'Montserrat', sans-serif;
      position: relative;
      overflow: hidden;
    }

    /* ── Fingerprint watermark ──────────────────────────────── */
    .fp-watermark {
      position: absolute;
      top: -60px;
      right: -100px;
      width: 520px;
      height: 580px;
      opacity: 0.055;
      pointer-events: none;
      z-index: 0;
    }

    /* ── Main content wrapper ───────────────────────────────── */
    .content {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      height: 100%;
      padding: 34px 46px 0;
    }

    /* ── HEADER ─────────────────────────────────────────────── */
    .header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;
    }

    .header-logo {
      width: 70px;
      height: 70px;
      object-fit: contain;
      flex-shrink: 0;
    }

    .header-text h1 {
      font-size: 20px;
      font-weight: 800;
      color: #1c2f7c;
      letter-spacing: 0.6px;
      line-height: 1.2;
    }

    .header-text p {
      font-size: 11px;
      color: #555;
      letter-spacing: 0.5px;
      margin-top: 3px;
      text-transform: uppercase;
    }

    /* ── CYON BANNER ────────────────────────────────────────── */
    .cyon-banner {
      background: #f6c100;
      padding: 14px 22px;
      text-align: center;
      margin-bottom: 18px;
    }

    .cyon-banner h2 {
      font-size: 24px;
      font-weight: 900;
      color: #1c2f7c;
      letter-spacing: 2.5px;
      line-height: 1.3;
      text-transform: uppercase;
    }

    /* ── PRESENT / HARVEST TITLE ────────────────────────────── */
    .present-block {
      text-align: center;
      margin-bottom: 14px;
    }

    .present-label {
      font-size: 11.5px;
      letter-spacing: 5px;
      color: #888;
      margin-bottom: 5px;
    }

    .harvest-title {
      font-size: 25px;
      font-weight: 900;
      color: #1c2f7c;
      letter-spacing: 2px;
      text-transform: uppercase;
    }

    /* ── CARD WRAPPER ───────────────────────────────────────────
       IMPORTANT: The photo lives here as a sibling of .blue-card,
       NOT inside it. This is intentional — it lets the photo bleed
       above the card freely while overflow:hidden on .blue-card
       still clips the card corners cleanly.
       The red bar is also a sibling so overflow:hidden can never
       clip it — guaranteeing full-width coverage.
    ────────────────────────────────────────────────────────── */
    .card-wrapper {
      position: relative;
      flex-shrink: 0;
      padding-top: 22px; /* room for photo to bleed above the card */
    }

    /* Portrait photo — bleeds above card via wrapper padding-top */
    .contestant-photo {
      position: absolute;
      left: 0;
      top: 0;
      width: 272px;
      height: 440px;
      object-fit: cover;
      object-position: top center;
      z-index: 4;
    }

    /* ── BLUE MAIN CARD ─────────────────────────────────────── */
    .blue-card {
      background: #1c2f7c;
      border-radius: 6px 6px 0 0; /* flat bottom so red bar butts flush */
      position: relative;
      height: 390px;
      overflow: hidden;            /* safe — photo is outside this element */
    }

    /* Theme text — right side of card only */
    .theme-block {
      position: absolute;
      left: 285px;
      top: 26px;
      right: 20px;
    }

    .theme-eyebrow {
      font-size: 11.5px;
      letter-spacing: 5px;
      color: rgba(255, 255, 255, 0.60);
      margin-bottom: 8px;
    }

    .theme-title {
      font-size: 52px;
      font-weight: 900;
      color: #ffffff;
      line-height: 0.93;
      text-transform: uppercase;
    }

    .theme-title .yellow { color: #f6c100; }

    .tagline {
      margin-top: 18px;
      font-size: 17px;
      color: rgba(255, 255, 255, 0.90);
      font-weight: 500;
      line-height: 1.45;
    }

    /* ── RED CONTESTANT BAR ─────────────────────────────────────
       Sibling of .blue-card — block element fills 100% wrapper
       width automatically. No clipping, no partial coverage.
    ────────────────────────────────────────────────────────── */
    .contestant-bar {
      position: relative;
      background: #c0161c;
      border-radius: 0 0 6px 6px;
      padding: 13px 18px 13px 296px;
      z-index: 3;
    }

    /* Gold arrow pointer */
    .contestant-bar::before {
      content: '';
      position: absolute;
      left: 275px;
      top: 50%;
      transform: translateY(-50%);
      width: 0;
      height: 0;
      border-top: 12px solid transparent;
      border-bottom: 12px solid transparent;
      border-left: 16px solid #f6c100;
    }

    .contestant-name {
      font-size: 20px;
      font-weight: 900;
      color: #ffffff;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      line-height: 1.2;
    }

    .contestant-role {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.88);
      margin-top: 2px;
      line-height: 1.35;
    }

    /* ── VOTE PRICING ROW ───────────────────────────────────── */
    .vote-section {
      padding: 14px 0 0 282px;
    }

    .vote-row {
      display: flex;
      gap: 8px;
    }

    .vote-btn {
      flex: 1;
      padding: 11px 6px;
      text-align: center;
      border-radius: 3px;
    }

    .vote-btn .v-amount {
      display: block;
      font-size: 15px;
      font-weight: 800;
    }

    .vote-btn .v-count {
      display: block;
      font-size: 12px;
      font-weight: 500;
      margin-top: 2px;
    }

    .vote-btn.gold  { background: #f6c100; color: #1c2f7c; }
    .vote-btn.navy  { background: #1c2f7c; color: #ffffff; }
    .vote-btn.red   { background: #c0161c; color: #ffffff; }
    .vote-btn.black { background: #111111; color: #ffffff; }

    .vote-note {
      font-size: 11.5px;
      color: #333;
      padding: 8px 0 0 282px;
    }

    /* ── FOOTER ─────────────────────────────────────────────── */
    .footer {
      background: #1c2f7c;
      margin: auto -46px 0;
      padding: 22px 46px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      flex-shrink: 0;
    }

    .footer-contact .f-label {
      font-size: 12.5px;
      color: rgba(255, 255, 255, 0.72);
      margin-bottom: 4px;
    }

    .footer-contact .f-phone {
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .footer-contact .f-phone::before {
      content: '📱';
      font-size: 18px;
    }

    .footer-message {
      text-align: center;
      font-size: 13px;
      color: #ffffff;
      line-height: 1.55;
      flex: 1;
    }

    .footer-message .vote-link {
      display: block;
      font-size: 11px;
      color: #8faeff;
      margin-top: 5px;
    }

    .footer-qr img {
      width: 82px;
      height: 82px;
      display: block;
      border: 3px solid #fff;
    }
  </style>
</head>
<body>

  <!-- Fingerprint watermark (concentric ellipse SVG) -->
  <svg class="fp-watermark" viewBox="0 0 400 450" fill="none" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="200" cy="225" rx="18"  ry="20"  stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="34"  ry="38"  stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="52"  ry="58"  stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="72"  ry="80"  stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="93"  ry="104" stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="116" ry="130" stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="140" ry="158" stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="166" ry="188" stroke="#000" stroke-width="2.5" fill="none"/>
    <ellipse cx="200" cy="225" rx="194" ry="220" stroke="#000" stroke-width="2.5" fill="none"/>
  </svg>

  <div class="content">

    <!-- Header -->
    <div class="header">
      <img class="header-logo" src="{{ logo_url }}" alt="Church Logo">
      <div class="header-text">
        <h1>CATHOLIC ARCHDIOCESE OF IBADAN</h1>
        <p>Christ the Good Shepherd Parish, Felele, Ibadan, Oyo State.</p>
      </div>
    </div>

    <!-- CYON Banner -->
    <div class="cyon-banner">
      <h2>Catholic Youth Organization<br>of Nigeria (CYON)</h2>
    </div>

    <!-- Present / Harvest -->
    <div class="present-block">
      <p class="present-label">P R E S E N T :</p>
      <h3 class="harvest-title">2026 Children and Youth Harvest</h3>
    </div>

    <!-- Card Wrapper: photo + blue card + red bar -->
    <div class="card-wrapper">

      <!-- Photo is a child of card-wrapper, NOT .blue-card -->
      <img class="contestant-photo" src="{{ photo_url }}" alt="{{ name }}">

      <!-- Blue card: theme text only -->
      <div class="blue-card">
        <div class="theme-block">
          <p class="theme-eyebrow">T H E M E :</p>
          <h2 class="theme-title">
            FUNDRAISING<br>
            AMBASSADOR<br>
            <span class="yellow">CHALLENGE</span>
          </h2>
          <p class="tagline">Support Our Harvest, Crown<br>a Champion.</p>
        </div>
      </div>

      <!-- Red bar: sibling of .blue-card, always full width -->
      <div class="contestant-bar">
        <div class="contestant-name">{{ name }}</div>
        <div class="contestant-role">{{ category }}</div>
      </div>

    </div><!-- .card-wrapper -->

    <!-- Vote Pricing -->
    <div class="vote-section">
      <div class="vote-row">
        <div class="vote-btn gold">
          <span class="v-amount">₦500</span>
          <span class="v-count">1 Vote</span>
        </div>
        <div class="vote-btn navy">
          <span class="v-amount">₦1,000</span>
          <span class="v-count">2 Votes</span>
        </div>
        <div class="vote-btn red">
          <span class="v-amount">₦5,000</span>
          <span class="v-count">10 Votes</span>
        </div>
        <div class="vote-btn black">
          <span class="v-amount">₦10,000</span>
          <span class="v-count">20 Votes</span>
        </div>
      </div>
    </div>
    <p class="vote-note">
      <strong>Note:</strong> There is no limit to the number of votes a supporter can cast.
    </p>

    <!-- Footer -->
    <div class="footer">
      <div class="footer-contact">
        <div class="f-label">For more enquiry contact:</div>
        <div class="f-phone">{{ contact_phone }}</div>
      </div>
      <div class="footer-message">
        I kindly invite you to support my campaign<br>
        And partner with us in this worthy cause.
        <span class="vote-link">{{ vote_url }}</span>
      </div>
      <div class="footer-qr">
        <img src="{{ qr_url }}" alt="QR Code">
      </div>
    </div>

  </div><!-- .content -->
</body>
</html>
```

---

## 4. Flyer Generator Utility

Save as `harvest/flyer_generator.py`.

```python
"""
harvest/flyer_generator.py
--------------------------
Core rendering logic: HTML template → Playwright screenshot → PNG bytes.
"""

import io
import os
import base64
import qrcode
from pathlib import Path

from playwright.sync_api import sync_playwright
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404
from django.conf import settings


# ── Optional: background removal ──────────────────────────────────────────────
# If rembg is installed, call strip_background() on upload to get a clean
# portrait cutout. Store the result as the contestant's display photo.

def strip_background(image_bytes: bytes) -> bytes:
    """Remove image background. Returns original bytes if rembg not installed."""
    try:
        from rembg import remove
        return remove(image_bytes)
    except ImportError:
        return image_bytes


# ── QR code → base64 data URI ─────────────────────────────────────────────────

def _make_qr_data_url(url: str) -> str:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


# ── Core render ───────────────────────────────────────────────────────────────

def render_flyer(
    name: str,
    photo_url: str,
    category: str,
    vote_url: str,
    contact_phone: str = "09134156737",
    logo_url: str = "",
) -> bytes:
    """
    Render the ambassador flyer and return raw PNG bytes.

    Args:
        name:          Contestant full name (will be uppercased).
        photo_url:     Absolute URL or base64 data URI of the contestant photo.
                       Ideally a background-removed PNG.
        category:      e.g. "Youth Category (Male): Most Influential Youth Fundraiser"
        vote_url:      Full URL to the contestant's voting page.
        contact_phone: Enquiry phone number shown in the footer.
        logo_url:      Absolute URL to the church/CYON logo. Falls back to
                       settings.HARVEST_LOGO_URL if empty.
    """
    context = {
        "name": name.upper(),
        "photo_url": photo_url,
        "category": category,
        "vote_url": vote_url,
        "contact_phone": contact_phone,
        "qr_url": _make_qr_data_url(vote_url),
        "logo_url": logo_url or getattr(settings, "HARVEST_LOGO_URL", ""),
    }

    html = render_to_string("flyers/ambassador_flyer.html", context)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        # wait_until="networkidle" ensures Google Fonts finish loading
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(600)  # extra buffer for layout paint
        png_bytes = page.screenshot(
            type="png",
            clip={"x": 0, "y": 0, "width": 1080, "height": 1080},
        )
        browser.close()

    return png_bytes


# ── Disk cache ────────────────────────────────────────────────────────────────

def get_or_generate_flyer(contestant) -> bytes:
    """
    Return cached PNG if it exists and is not stale, otherwise generate + cache.
    Set contestant.flyer_dirty = True (and save) whenever name or photo changes.
    """
    cache_dir = Path(settings.MEDIA_ROOT) / "flyers"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{contestant.pk}.png"

    if cache_path.exists() and not getattr(contestant, "flyer_dirty", False):
        return cache_path.read_bytes()

    png = render_flyer(
        name=contestant.full_name,
        photo_url=contestant.get_photo_absolute_url(),
        category=contestant.get_category_label(),
        vote_url=contestant.get_absolute_vote_url(),
        contact_phone=getattr(settings, "HARVEST_CONTACT_PHONE", "09134156737"),
        logo_url=getattr(settings, "HARVEST_LOGO_URL", ""),
    )

    cache_path.write_bytes(png)

    # Mark cache as fresh
    type(contestant).objects.filter(pk=contestant.pk).update(flyer_dirty=False)

    return png


# ── Django view ───────────────────────────────────────────────────────────────

def flyer_view(request, pk: int):
    """
    GET /harvest/flyer/<pk>/        → inline PNG (for sharing/preview)
    GET /harvest/flyer/<pk>/?download=1  → file download
    """
    from .models import Contestant  # adjust to your actual import

    try:
        contestant = Contestant.objects.get(pk=pk, approved=True)
    except Contestant.DoesNotExist:
        raise Http404

    png_bytes = get_or_generate_flyer(contestant)

    disposition = "attachment" if request.GET.get("download") else "inline"
    safe_name = contestant.full_name.replace(" ", "_")
    filename = f"flyer_{safe_name}.png"

    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "max-age=3600, private"
    return response
```

---

## 5. URL Configuration

Add to `harvest/urls.py`:

```python
from django.urls import path
from .flyer_generator import flyer_view

urlpatterns = [
    # ... your existing urls ...
    path("flyer/<int:pk>/", flyer_view, name="contestant-flyer"),
]
```

Ensure `harvest/urls.py` is included in your project's `urls.py`:

```python
# project/urls.py
from django.urls import path, include

urlpatterns = [
    path("harvest/", include("harvest.urls")),
    # ...
]
```

---

## 6. Model

Add these fields and methods to your `Contestant` model:

```python
# harvest/models.py
from django.db import models
from django.urls import reverse

CATEGORY_CHOICES = [
    ("youth_male",   "Youth Category (Male): Most Influential Youth Fundraiser"),
    ("youth_female", "Youth Category (Female): Most Influential Youth Fundraiser"),
    ("child_male",   "Children Category (Male): Most Influential Child Fundraiser"),
    ("child_female", "Children Category (Female): Most Influential Child Fundraiser"),
]

class Contestant(models.Model):
    full_name    = models.CharField(max_length=200)
    photo        = models.ImageField(upload_to="contestants/")
    category     = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    approved     = models.BooleanField(default=False)
    flyer_dirty  = models.BooleanField(default=True)  # True = cache stale

    def get_category_label(self) -> str:
        return dict(CATEGORY_CHOICES).get(self.category, self.category)

    def get_absolute_vote_url(self) -> str:
        path = reverse("vote", args=[self.pk])          # adjust view name
        return f"https://{settings.ALLOWED_HOSTS[0]}{path}"

    def get_photo_absolute_url(self) -> str:
        """Returns an absolute URL the headless browser can reach."""
        return f"https://{settings.ALLOWED_HOSTS[0]}{self.photo.url}"

    def save(self, *args, **kwargs):
        # Bust flyer cache whenever name or photo changes
        if self.pk:
            try:
                old = Contestant.objects.get(pk=self.pk)
                if old.full_name != self.full_name or old.photo != self.photo:
                    self.flyer_dirty = True
            except Contestant.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name
```

After adding the model, run:

```bash
python manage.py makemigrations harvest
python manage.py migrate
```

---

## 7. Settings

Add to `settings.py`:

```python
# CYON Harvest flyer settings
HARVEST_CONTACT_PHONE = "09134156737"
HARVEST_LOGO_URL      = "https://yoursite.com/static/images/church_logo.png"

# Ensure media files are served in development
# (production should serve via nginx)
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

Add media URL serving to `project/urls.py` for **development only**:

```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... your routes ...
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 8. Photo Upload: Background Removal on Save

To automatically strip the photo background when a contestant is uploaded,
add a signal or override `save()` on the model:

```python
# harvest/models.py  (add inside Contestant.save(), after super().save())

from .flyer_generator import strip_background
from PIL import Image
import io

def save(self, *args, **kwargs):
    # ... existing dirty-flag logic ...
    super().save(*args, **kwargs)

    # Strip background if this is a new photo (png output)
    if self.photo and self.flyer_dirty:
        img_path = self.photo.path
        with open(img_path, "rb") as f:
            original = f.read()
        cleaned = strip_background(original)  # no-op if rembg not installed
        with open(img_path, "wb") as f:
            f.write(cleaned)
```

---

## 9. Usage in Admin or Management Command

```python
# Manually regenerate a flyer (e.g. from Django shell or management command)
from harvest.models import Contestant
from harvest.flyer_generator import render_flyer

c = Contestant.objects.get(pk=1)
png = render_flyer(
    name=c.full_name,
    photo_url=c.get_photo_absolute_url(),
    category=c.get_category_label(),
    vote_url=c.get_absolute_vote_url(),
)

with open(f"/tmp/flyer_{c.pk}.png", "wb") as f:
    f.write(png)
print("Done.")
```

---

## 10. Key Design Decisions (Do Not Change)

| Decision | Reason |
|---|---|
| Photo is **outside** `.blue-card` in the HTML | `overflow:hidden` on `.blue-card` would clip the photo's top bleed AND the red bar's bottom corners if photo were inside |
| `.contestant-bar` is a **sibling** of `.blue-card` | Block element fills 100% wrapper width automatically — no `position:absolute`, no clipping possible |
| `.blue-card` has `border-radius: 6px 6px 0 0` (top only) | Flat bottom so the red bar butts flush with no gap |
| `.contestant-bar` has `border-radius: 0 0 6px 6px` (bottom only) | Completes the card's rounded corner appearance at the bottom |
| `wait_until="networkidle"` in Playwright | Required so Google Fonts (Montserrat) finish loading before screenshot |
| QR code rendered as base64 data URI | Avoids the headless browser making an outbound HTTP request for the QR image |
| `flyer_dirty` flag on model | Prevents regenerating the PNG on every request; only regenerates when name or photo actually changes |
