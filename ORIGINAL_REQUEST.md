# Original User Request

## Initial Request — 2026-06-10T13:39:45+01:00

Project: Refine and expand Phase 5 (Custom Admin Dashboard + Smart Autocomplete) for the CYON Harvest Portal. Implement the provided multi-agent architecture to add filters, fix desktop UI constraints, and modularize the Javascript.

Working directory: c:\Users\USER\Documents\python_codes\cgscc_cyon
Integrity mode: development

## Requirements

### R1. Data & API
- Update `Parishioner` model in `contributions/models.py` to include `source` (choices: registry/manual) and `created_at`.
- Create and apply migrations. Register `Parishioner` in `contributions/admin.py` with `list_display`, `search_fields`, and `list_filter`.
- Update the GET view at `/api/names/search/?q=` to require login, merge Parishioner and Contribution names, deduplicate, and return exactly 5 results as JSON.

### R2. Dashboard & Filters
- Update `master_dashboard` and `export_csv` in `dashboard/views.py` to accept GET params (`method`, `date_from`, `date_to`) and filter the `Contribution` queryset accordingly.
- Compute 6 stat metrics: Total Raised, Progress % (target 5M), Cash, POS, Transfer, Pledges.
- Revamp `templates/dashboard/master.html`: Remove the narrow constraints so it looks great on desktop, use a 6-card CSS grid row for metrics, add the filter form (preserving state), and style the data table.

### R3. Autocomplete Frontend
- Move the autocomplete logic into `static/js/autocomplete.js`.
- Implement debounced AJAX typeahead (300ms) that creates a DOM dropdown, fetches from the API, and populates the `name` input on click.
- Handle click-away and Escape key closures. Focus the `amount` input after selection.
- Update `donation_form.html` to load the external script.

## Verification Resources
- The Django project is fully scaffolded and running locally.
- Agents can verify models via Django shell or by checking the local SQLite database.

## Acceptance Criteria

### Data & API
- [ ] `Parishioner` model has the new fields and is visible in Django Admin.
- [ ] Search endpoint returns a valid JSON array of up to 5 names when queried.

### Dashboard UI
- [ ] The dashboard renders full-width on desktop without horizontal squishing.
- [ ] Submitting the filter form updates the URL query params and correctly filters the table and CSV export.
- [ ] The 6 metric cards display accurate aggregates based on the filtered queryset.

### Autocomplete Frontend
- [ ] Typing in the name field triggers a network request after 300ms.
- [ ] Clicking a suggestion fills the input, hides the dropdown, and moves focus to the amount field.
- [ ] `autocomplete.js` is loaded externally with zero inline JS remaining for the search logic.

## Follow-up — 2026-06-12T09:50:50+01:00

Adjust the landing page of the CYON Harvest portal for mobile view (widths from 320px to 768px) to make it highly responsive, visually impressive, and premium, using the details from the desktop view but making it display nicely on mobile.

Working directory: c:/Users/USER/Documents/python_codes/cgscc_cyon
Integrity mode: development

## Requirements

### R1. Topbar and Branding Mobile Layout
On mobile devices (<= 768px), keep both the Archdiocese seal and the CYON logo on the edges of the topbar, but make them significantly smaller (e.g., Archdiocese seal: 45px, CYON logo: 50px). Ensure the church name text in the center is readable and scales down to fit between the two logos without wrapping awkwardly or overflowing the topbar boundary.

### R2. Hero Headline and Target Widget Layout
Ensure the hero script ("Join us to"), headline ("REACH OUR HARVEST TARGET"), and progress widget are centered and fit the screen without clipping:
- The target amount `₦5,000,000` must scale down using responsive typography (e.g. `clamp(2rem, 7vw, 4.2rem)`) so it never clips or wraps.
- The secondary parish target label (`Part of the parish-wide target of ₦30,000,000`) must layout neatly (e.g. allow wrapping or structure cleanly) to prevent horizontal scrolling.

### R3. Hero CTA Buttons Mobile Stack
On mobile, the two main CTA buttons ("Donate / Pledge Now" and "View Live Board") should stack vertically for a thumb-friendly layout, but they should **not** occupy the full width of the mobile screen. Constrain them to a centered container with a max-width (e.g., `max-width: 280px` or `300px`, or `80%` width) and add a small vertical gap between them.

### R4. Grid Layout and Card Adjustments
Optimize the padding and spacing of sections on mobile:
- Reduce section padding from `5rem 2.5rem` to `3rem 1.25rem`.
- Reduce card paddings in the `Why` and `Donate` sections (e.g., from `2.5rem` to `1.5rem`) to maximize screen width.
- Switch the donate grid to a single column as configured, ensuring both cards look visually balanced and are centered.

### R5. Bank Account Number Responsive Font Size
On mobile screens (down to 320px), the 10-digit account number (`0000313701`) must scale down proportionally (e.g., using a font-size like `clamp(1.6rem, 6vw, 2.5rem)` and reducing letter-spacing to `1px` or `2px`) so that it fits entirely within the bank card container without horizontal overflow.

## Acceptance Criteria

### Responsiveness & Design Quality
- [ ] No horizontal overflow on screens down to 320px width (no horizontal scrollbar on the page body).
- [ ] Both logos remain visible on the left and right edges of the topbar, scaled down, with the church name positioned in between them without overlapping.
- [ ] Hero CTA buttons are stacked vertically, centered, and do not occupy the full width of the screen.
- [ ] Target amount `₦5,000,000` is fully visible and does not clip or overflow its parent widget on a 360px screen.
- [ ] Bank account number `0000313701` fits completely within the bank card container on a 360px screen.
- [ ] Staggered CSS reveal animations remain smooth and do not cause jumpy layout shifts on mobile.

## Follow-up — 2026-06-21T22:04:26+01:00

# Teamwork Project Prompt

> Status: Launched
> Goal: Execute the custom admin dashboard development

Build a robust custom admin dashboard to manage the platform's overall processes, specifically focusing on payment history with the ability to approve, verify, reject, and re-query transactions.

Working directory: c:/Users/USER/Documents/python_codes/cgscc_cyon
Integrity mode: development

## Requirements

### R1. Tech Stack & Version Control
The agent team is free to decide the optimal frontend technology stack (e.g., React, plain HTML/JS) to build a highly responsive and robust admin dashboard, utilizing Tailwind CSS for maximum styling flexibility. All work must be conducted on a new, separate branch from `main`.

### R2. Backend Integration
The dashboard must integrate with the existing backend API to fetch payment history and perform actions (approve, verify, reject).

### R3. Payment Gateway Integration
The "re-query" functionality must directly hit the external payment gateway's API to retrieve real-time transaction status.

## Acceptance Criteria

### Verification & Testing
- [ ] The dashboard successfully displays a list of transactions (using mock data for testing if a local backend isn't available).
- [ ] Clicking 'approve', 'verify', or 'reject' triggers the correct API payload to the backend and updates the UI state without a full page refresh.
- [ ] Clicking 're-query' correctly formats and sends a request intended for the payment gateway API, updating the UI with the mocked or real response.
- [ ] The dashboard is fully responsive on mobile devices using Tailwind CSS.
