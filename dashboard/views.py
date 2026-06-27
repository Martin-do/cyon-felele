import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from accounts.models import Member
from contributions.models import Contribution
from django.contrib import messages
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import requests
from django.conf import settings
from collections import OrderedDict
from contributions.serializers import ContributionSerializer

@login_required(login_url='/accounts/login/')
def member_hub_view(request):
    from contributions.models import InflowCategory

    user = request.user
    
    if not user.has_completed_onboarding:
        return redirect('accounts:onboarding')
    
    if request.method == 'POST':
        pass

    referred_contributions = Contribution.objects.filter(referred_by=user, is_voided=False, status='approved')
    total_referred = referred_contributions.aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    progress_percentage = 0
    if user.levy_amount > 0:
        progress_percentage = min(int((user.levy_paid / user.levy_amount) * 100), 100)

    # Global Campaign Progress for Progress Bar
    all_approved = Contribution.objects.filter(is_voided=False, status='approved')
    total_campaign_raised = all_approved.aggregate(Sum('amount'))['amount__sum'] or 0.00
    global_progress = min(round((float(total_campaign_raised) / 5000000.0) * 100, 1), 100)
    if total_campaign_raised > 0 and global_progress < 1:
        global_progress = 1  # Show at least 1% when there are contributions

    category_stats = []
    colors = ['#3b82f6', '#f43f5e', '#a855f7', '#6366f1', '#14b8a6']
    active_categories = InflowCategory.objects.filter(is_active=True)
    
    color_idx = 0
    for cat in active_categories:
        cat_total = all_approved.filter(inflow_category=cat).aggregate(Sum('amount'))['amount__sum'] or 0.00
        if cat_total > 0:
            lower_name = cat.name.lower()
            if 'campaign funds' in lower_name or 'cash' in lower_name:
                assigned_color = '#10b981' # emerald-500
            elif 'pledge' in lower_name:
                assigned_color = '#f59e0b' # amber-500
            else:
                assigned_color = colors[color_idx % len(colors)]
                color_idx += 1
                
            category_stats.append({
                'name': cat.name,
                'amount': float(cat_total),
                'percent': (float(cat_total) / 5000000.0) * 100,
                'color': assigned_color
            })
    
    category_stats.sort(key=lambda x: x['amount'], reverse=True)

    base_url = request.build_absolute_uri('/')[:-1] 
    referral_link = f"{base_url}/support/{user.referral_slug}/"

    context = {
        'total_referred': total_referred,
        'recent_referrals': referred_contributions.order_by('-timestamp')[:5],
        'progress_percentage': progress_percentage,
        'total_campaign_raised': total_campaign_raised,
        'global_progress': global_progress,
        'category_stats': category_stats,
        'referral_link': referral_link,
        'member': user,
    }
    return render(request, 'dashboard/member_hub.html', context)

@login_required(login_url='/accounts/login/')
def redeem_pledge_view(request):
    from contributions.models import Pledge, Contribution
    
    if request.method == 'POST':
        pledge_id = request.POST.get('pledge_id')
        amount = request.POST.get('amount')
        method = request.POST.get('method') # 'Transfer' or 'Online'
        
        pledge = get_object_or_404(Pledge, pk=pledge_id, member=request.user)
        
        # Create a pending contribution
        import uuid as uuid_module
        contribution = Contribution.objects.create(
            idempotency_key=uuid_module.uuid4(),
            name=request.user.name,
            phone=request.user.identifier,
            amount=amount,
            method=method,
            source='member_hub',
            status='pending',
            referred_by=request.user,
            inflow_category=pledge.inflow_category,
            pledge=pledge
        )
        
        if method == 'Online':
            # Redirect to Paystack or handle online payment later
            messages.info(request, "Online payment for pledge redemption will be processed. (Paystack Integration Pending)")
            return redirect('dashboard:my_pledges')
        else:
            messages.success(request, f"Your manual transfer of ₦{amount} towards your pledge has been logged. It is now pending approval by an admin.")
            return redirect('dashboard:my_pledges')

    return redirect('dashboard:my_pledges')

@login_required(login_url='/accounts/login/')
def generate_flyer_view(request):
    user = request.user
    
    if user.custom_flyer:
        try:
            from django.http import FileResponse
            response = FileResponse(user.custom_flyer.open(), content_type="image/jpeg")
            response['Content-Disposition'] = f'attachment; filename="flyer_{user.name.replace(" ", "_")}.jpg"'
            return response
        except Exception:
            pass

    import os
    from django.conf import settings
    from django.http import HttpResponse
    
    # Define cache path
    flyers_dir = os.path.join(settings.MEDIA_ROOT, 'flyers')
    os.makedirs(flyers_dir, exist_ok=True)
    cache_path = os.path.join(flyers_dir, f"{user.id}.png")
    
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            response = HttpResponse(f.read(), content_type="image/png")
            response['Content-Disposition'] = f'attachment; filename="flyer_{user.name.replace(" ", "_")}.png"'
            return response

    # If not cached, generate using Playwright
    from django.template.loader import render_to_string
    from playwright.sync_api import sync_playwright
    import base64
    
    # Base64 encode the logo
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'brand', 'cyon-logo.png')
    try:
        with open(logo_path, "rb") as img_file:
            bg_b64 = base64.b64encode(img_file.read()).decode('utf-8')
            cyon_logo_base64 = f"data:image/png;base64,{bg_b64}"
    except Exception:
        cyon_logo_base64 = ""

    # Base64 encode the profile picture
    photo_base64 = ""
    if user.profile_picture:
        try:
            with open(user.profile_picture.path, "rb") as img_file:
                original_bytes = img_file.read()
            
            # Strip background
            try:
                import os
                from django.conf import settings
                u2net_path = os.path.join(settings.MEDIA_ROOT, 'u2net')
                os.makedirs(u2net_path, exist_ok=True)
                os.environ['U2NET_HOME'] = u2net_path
                
                from rembg import remove, new_session
                session = new_session("u2net")
                cleaned_bytes = remove(original_bytes, session=session)
            except BaseException:
                cleaned_bytes = original_bytes
                
            photo_b64 = base64.b64encode(cleaned_bytes).decode('utf-8')
            photo_base64 = f"data:image/png;base64,{photo_b64}"
        except Exception:
            pass

    title = user.contestant_title if user.contestant_title and user.contestant_title != 'None' else "CYON AMBASSADOR"
    
    # Generate vote_url and QR code
    base_url = request.build_absolute_uri('/')[:-1] 
    vote_url = f"{base_url}/support/{user.referral_slug}/"
    
    import qrcode
    import io
    img = qrcode.make(vote_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    qr_url = f"data:image/png;base64,{qr_b64}"
        
    html_content = render_to_string('dashboard/flyer.html', {
        'name': user.name,
        'photo_url': photo_base64,
        'logo_url': cyon_logo_base64,
        'category': title,
        'vote_url': vote_url,
        'contact_phone': "09134156737",
        'qr_url': qr_url,
    })
    
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.set_content(html_content, wait_until="load", timeout=30000)
            page.wait_for_timeout(1500) # Give it 1.5s to render Google Fonts just in case
            img_bytes = page.screenshot(type="png")
            browser.close()
            
        # Cache it
        with open(cache_path, "wb") as f:
            f.write(img_bytes)
            
        response = HttpResponse(img_bytes, content_type="image/png")
        response['Content-Disposition'] = f'attachment; filename="flyer_{user.name.replace(" ", "_")}.png"'
        return response
    except Exception as e:
        return HttpResponse(f"Error generating flyer with Playwright: {str(e)}", status=500)

@login_required(login_url='/accounts/login/')
def generate_qr_code_view(request):
    user = request.user
    base_url = request.build_absolute_uri('/')[:-1] 
    referral_link = f"{base_url}/support/{user.referral_slug}/"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(referral_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E3A8A", back_color="transparent")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")

def leaderboard_view(request):
    members = Member.objects.filter(is_active=True, is_staff=False)
    youth_leaderboard = []
    children_leaderboard = []
    
    for member in members:
        total = Contribution.objects.filter(referred_by=member, is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
        if total > 0:
            entry = {
                'name': member.name,
                'total': total,
                'votes': int(total // 500),
                'gender': member.gender,
                'title': member.contestant_title
            }
            if member.contestant_title in ['Master Harvest', 'Miss Harvest']:
                children_leaderboard.append(entry)
            else:
                youth_leaderboard.append(entry)
            
    youth_leaderboard = sorted(youth_leaderboard, key=lambda x: x['total'], reverse=True)
    children_leaderboard = sorted(children_leaderboard, key=lambda x: x['total'], reverse=True)
    
    total_harvest = Contribution.objects.filter(is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    context = {
        'youth_leaderboard': youth_leaderboard,
        'children_leaderboard': children_leaderboard,
        'total_harvest': total_harvest
    }
    return render(request, 'dashboard/leaderboard.html', context)

@login_required(login_url='/accounts/login/')
def my_pledges_view(request):
    from contributions.models import Pledge, InflowCategory
    
    user = request.user
    my_pledges = Pledge.objects.filter(member=user).exclude(status='voided').order_by('-timestamp')
    categories = InflowCategory.objects.all()
    
    # Calculate balances
    for pledge in my_pledges:
        pledge.balance = pledge.amount_pledged - pledge.amount_fulfilled
        
    context = {
        'my_pledges': my_pledges,
        'categories': categories,
    }
    return render(request, 'dashboard/my_pledges.html', context)

@login_required(login_url='/accounts/login/')
def create_self_pledge_view(request):
    from contributions.models import Pledge, InflowCategory
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        category_id = request.POST.get('category_id')
        note = request.POST.get('note')
        
        category = InflowCategory.objects.get(id=category_id) if category_id else None
        
        Pledge.objects.create(
            member=request.user,
            name=request.user.name,
            phone=request.user.identifier,
            amount_pledged=amount,
            inflow_category=category,
            note=note,
            status='pending' # Needs admin approval
        )
        
        messages.success(request, "Your pledge has been submitted and is pending admin approval. Thank you!")
        
    return redirect('dashboard:my_pledges')

import csv
from django.http import HttpResponse
from functools import wraps
from contributions.models import InflowCategory
from accounts.models import PinResetRequest

def admin_required(view_func):
    @wraps(view_func)
    @login_required(login_url='/dashboard/login/')
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_admin_user:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard:member_hub')
    return _wrapped_view

def approver_required(view_func):
    @wraps(view_func)
    @login_required(login_url='/accounts/login/')
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_approver:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access denied. Approver privileges required.")
        return redirect('dashboard:member_hub')
    return _wrapped_view

def usher_required(view_func):
    @wraps(view_func)
    @login_required(login_url='/accounts/login/')
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_usher:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access denied. Usher privileges required.")
        return redirect('dashboard:member_hub')
    return _wrapped_view

@admin_required
def master_dashboard_view(request):
    contributions = Contribution.objects.filter(is_voided=False, status='approved').order_by('-timestamp')
    
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    category_id = request.GET.get('category_id', '')

    if method and method != 'All':
        contributions = contributions.filter(method__icontains=method)
    
    if category_id and category_id != 'All':
        contributions = contributions.filter(inflow_category_id=category_id)
    
    if date_from:
        try:
            contributions = contributions.filter(timestamp__date__gte=date_from)
        except Exception:
            pass

    if date_to:
        try:
            contributions = contributions.filter(timestamp__date__lte=date_to)
        except Exception:
            pass

    total_amount = contributions.aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    target_amount = 5000000
    progress_percentage = min(round((total_amount / target_amount) * 100, 1), 100) if total_amount else 0
    if total_amount > 0 and progress_percentage < 1:
        progress_percentage = 1  # Show at least 1% when there are contributions

    cash_total = contributions.filter(method__icontains='Cash').aggregate(Sum('amount'))['amount__sum'] or 0.00
    transfer_total = contributions.filter(method__icontains='Transfer').aggregate(Sum('amount'))['amount__sum'] or 0.00
    pledge_total = contributions.filter(method__icontains='Pledge').aggregate(Sum('amount'))['amount__sum'] or 0.00

    categories = InflowCategory.objects.all()
    members = Member.objects.filter(is_active=True).order_by('name')
    pin_requests = PinResetRequest.objects.filter(is_resolved=False).order_by('-created_at')
    resolved_resets = PinResetRequest.objects.filter(is_resolved=True).order_by('-resolved_at')[:10]

    from contributions.models import Pledge
    pending_pledges = Pledge.objects.filter(status='pending').order_by('-timestamp')
    approved_pledges = Pledge.objects.filter(status='approved').order_by('-timestamp')

    context = {
        'contributions': contributions,
        'total_amount': total_amount,
        'progress_percentage': progress_percentage,
        'cash_total': cash_total,
        'transfer_total': transfer_total,
        'pledge_total': pledge_total,
        'method': method,
        'date_from': date_from,
        'date_to': date_to,
        'category_id': category_id,
        'categories': categories,
        'members': members,
        'pin_requests': pin_requests,
        'resolved_resets': resolved_resets,
        'query_string': request.GET.urlencode(),
        'pending_pledges': pending_pledges,
        'approved_pledges': approved_pledges,
    }
    return render(request, 'dashboard/admin_master.html', context)

@admin_required
def export_csv_view(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="harvest_contributions.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Name', 'Phone', 'Amount', 'Method', 'Source', 'Referred By', 'Anonymous', 'Date'])
    
    contributions = Contribution.objects.filter(is_voided=False, status='approved').order_by('timestamp')
    
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    category_id = request.GET.get('category_id', '')

    if method and method != 'All':
        contributions = contributions.filter(method__icontains=method)
    
    if category_id and category_id != 'All':
        contributions = contributions.filter(inflow_category_id=category_id)
    
    if date_from:
        try:
            contributions = contributions.filter(timestamp__date__gte=date_from)
        except Exception:
            pass

    if date_to:
        try:
            contributions = contributions.filter(timestamp__date__lte=date_to)
        except Exception:
            pass

    for c in contributions:
        referrer = c.referred_by.name if c.referred_by else ''
        writer.writerow([
            str(c.id)[:8], c.name, c.phone, c.amount, c.method, 
            c.source, referrer, 'Yes' if c.is_anonymous else 'No', 
            c.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        ])
        
    return response

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@approver_required
def approval_center_view(request):
    pending_contributions = Contribution.objects.filter(is_voided=False, status='pending').order_by('-timestamp')
    context = {
        'contributions': pending_contributions,
    }
    return render(request, 'dashboard/approval_center.html', context)

def send_whatsapp_approval_notice(request, contribution):
    # Disabled for now to avoid WhatsApp spam/anti-ban issues.
    pass

@approver_required
def approve_contribution_view(request, pk):
    if request.method == 'POST':
        contribution = get_object_or_404(Contribution, pk=pk)
        contribution.status = 'approved'
        contribution.save()
        
        # If this contribution is tied to a pledge, update the fulfilled amount
        if contribution.pledge:
            contribution.pledge.amount_fulfilled += contribution.amount
            contribution.pledge.save()
        
        # Trigger Web Push notification
        send_approval_push_notification(contribution)
        
        # Trigger WhatsApp notification notice
        send_whatsapp_approval_notice(request, contribution)
        
        messages.success(request, f"Approved contribution from {contribution.name}.")
    return redirect('dashboard:approval_center')

@approver_required
def reject_contribution_view(request, pk):
    if request.method == 'POST':
        contribution = get_object_or_404(Contribution, pk=pk)
        contribution.status = 'rejected'
        contribution.save()
        messages.info(request, f"Rejected contribution from {contribution.name}.")
    return redirect('dashboard:approval_center')

@usher_required
def live_entry_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        amount = request.POST.get('amount')
        method = request.POST.get('method', 'Cash')
        phone = request.POST.get('phone', '')
        referred_by_id = request.POST.get('referred_by', '')
        category_id = request.POST.get('category', '')
        
        referrer = None
        if referred_by_id:
            try:
                referrer = Member.objects.get(id=referred_by_id)
            except Member.DoesNotExist:
                pass
        
        category = None
        if category_id:
            try:
                category = InflowCategory.objects.get(id=category_id)
            except InflowCategory.DoesNotExist:
                pass
                
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
                'recorder_id': request.user.identifier,
            }
        )
        if not created:
            messages.warning(request, "Duplicate submission detected — entry already recorded.")
            return redirect('dashboard:live_entry')
            
        messages.success(request, f"Successfully recorded {method} payment from {name}.")
        return redirect('dashboard:live_entry')
        
    members = Member.objects.filter(is_active=True).order_by('name')
    categories = InflowCategory.objects.filter(is_active=True)
    context = {
        'members': members,
        'categories': categories,
    }
    return render(request, 'dashboard/live_entry.html', context)



class AdminTransactionPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        response_data = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ])
        stats = getattr(self, 'statistics', {})
        for key, val in stats.items():
            response_data[key] = val
        return Response(response_data)


class AdminTransactionListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        queryset = Contribution.objects.filter(is_voided=False)

        method = request.query_params.get('method')
        status_val = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        category_id = request.query_params.get('category_id')

        if method:
            queryset = queryset.filter(method__icontains=method)
        if status_val:
            queryset = queryset.filter(status=status_val)
        if category_id:
            queryset = queryset.filter(inflow_category_id=category_id)
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        # Single database aggregation pass using Sum with filter=Q(...) conditional aggregations
        stats = queryset.aggregate(
            total_raised=Sum('amount'),
            cash=Sum('amount', filter=Q(method__icontains='Cash')),
            transfer=Sum('amount', filter=Q(method__icontains='Transfer')),
            pledges=Sum('amount', filter=Q(method__icontains='Pledge')),
            paystack=Sum('amount', filter=Q(method__icontains='Paystack') | Q(method__icontains='Online')),
        )

        total_raised = float(stats['total_raised'] or 0.0)
        cash = float(stats['cash'] or 0.0)
        transfer = float(stats['transfer'] or 0.0)
        pledges = float(stats['pledges'] or 0.0)
        paystack = float(stats['paystack'] or 0.0)

        target = 5000000
        progress_percentage = min(int((total_raised / target) * 100), 100) if total_raised > 0 else 0

        # Fetch all active categories and sum amounts for this queryset
        from contributions.models import InflowCategory
        category_stats = {}
        for category in InflowCategory.objects.filter(is_active=True):
            category_stats[f"cat_{category.id}"] = float(queryset.filter(inflow_category=category).aggregate(total=Sum('amount'))['total'] or 0.0)

        # Include uncategorized payments
        category_stats["uncategorized"] = float(queryset.filter(inflow_category__isnull=True).aggregate(total=Sum('amount'))['total'] or 0.0)

        statistics = {
            'total_raised': total_raised,
            'cash': cash,
            'transfer': transfer,
            'pledges': pledges,
            'paystack': paystack,
            'progress_percentage': progress_percentage,
            'category_stats': category_stats
        }

        queryset = queryset.order_by('-timestamp')

        paginator = AdminTransactionPagination()
        paginator.statistics = statistics
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ContributionSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = ContributionSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class ContributionActionAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        contribution = get_object_or_404(Contribution, pk=pk)
        
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        if action not in ['approve', 'verify', 'reject']:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        if action in ['approve', 'verify']:
            contribution.status = 'approved'
            contribution.save()

            # Trigger Web Push notification
            send_approval_push_notification(contribution)

            # Trigger WhatsApp notification notice
            send_whatsapp_approval_notice(request, contribution)

            # Trigger WebSocket push for Live Board
            channel_layer = get_channel_layer()
            total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
            display_name = 'Anonymous' if contribution.is_anonymous else contribution.name
            
            ws_data = {
                'id': str(contribution.id),
                'name': display_name,
                'amount': str(contribution.amount),
                'method': contribution.method,
                'source': contribution.source,
                'timestamp': contribution.timestamp.isoformat(),
                'total_harvest': str(total)
            }
            
            async_to_sync(channel_layer.group_send)(
                'live_board',
                {
                    'type': 'new_contribution',
                    'data': ws_data
                }
            )

        elif action == 'reject':
            contribution.status = 'rejected'
            contribution.save()

            print(f"NOTIFICATION: Contribution from {contribution.name} ({contribution.phone}) was rejected. Reason: {reason}.")

        return Response({'status': 'success', 'contribution_status': contribution.status})


class RequeryPaystackTransactionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        contribution = get_object_or_404(Contribution, pk=pk)

        if not contribution.method or contribution.method.lower() != 'paystack':
            return Response({'error': "Transaction method is not 'Paystack'"}, status=status.HTTP_400_BAD_REQUEST)

        if not contribution.idempotency_key:
            return Response({'error': "Transaction does not have an idempotency key"}, status=status.HTTP_400_BAD_REQUEST)

        secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        if contribution.inflow_category and contribution.inflow_category.api_key_name:
            secret_key = getattr(settings, contribution.inflow_category.api_key_name, secret_key)

        url = f"https://api.paystack.co/transaction/verify/{contribution.idempotency_key}"
        headers = {
            "Authorization": f"Bearer {secret_key}",
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            res_data = response.json()
        except requests.RequestException as e:
            return Response({'error': f"Connection to Paystack failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({'error': "Invalid JSON response from Paystack API"}, status=status.HTTP_502_BAD_GATEWAY)

        paystack_status = res_data.get('status')
        data = res_data.get('data', {})
        data_status = data.get('status') if data else None

        if paystack_status is True and data_status == 'success':
            contribution.status = 'approved'
            contribution.save()

            # Fire Django Channels push
            channel_layer = get_channel_layer()
            total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
            display_name = 'Anonymous' if contribution.is_anonymous else contribution.name
            
            ws_data = {
                'id': str(contribution.id),
                'name': display_name,
                'amount': str(contribution.amount),
                'method': contribution.method,
                'source': contribution.source,
                'timestamp': contribution.timestamp.isoformat(),
                'total_harvest': str(total)
            }
            
            async_to_sync(channel_layer.group_send)(
                'live_board',
                {
                    'type': 'new_contribution',
                    'data': ws_data
                }
            )

            return Response({'status': 'success', 'contribution_status': contribution.status})
        elif data_status == 'failed':
            contribution.status = 'rejected'
            contribution.save()
            return Response({'status': 'failed', 'contribution_status': contribution.status, 'error': 'Payment failed on Paystack'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'status': 'pending_or_other',
                'paystack_status': data_status or 'unknown',
                'message': 'Payment is not successful or failed yet'
            })


def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_admin_user:
        return redirect('dashboard:master_dashboard')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        password = request.POST.get('password')

        user = authenticate(request, username=identifier, password=password)
        if user is not None:
            if user.is_admin_user:
                auth_login(request, user)
                messages.success(request, f'Welcome back, Admin {user.name}!')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('dashboard:master_dashboard')
            else:
                messages.error(request, 'Access denied. Only administrators are allowed.')
        else:
            messages.error(request, 'Invalid identifier or password.')

    return render(request, 'dashboard/admin_login.html', {'next': next_url})

import random
from django.utils import timezone

@admin_required
def update_member_role_view(request, pk):
    if request.method == 'POST':
        member = get_object_or_404(Member, pk=pk)
        role = request.POST.get('role')
        if role in dict(Member.ROLE_CHOICES):
            member.role = role
            # If role is admin, also grant is_staff for admin site access
            if role == 'admin':
                member.is_staff = True
            member.save()
            messages.success(request, f"Updated role for {member.name} to {member.get_role_display()}.")
        else:
            messages.error(request, "Invalid role selected.")
    return redirect('dashboard:master_dashboard')

@admin_required
def add_inflow_category_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            if not InflowCategory.objects.filter(name__iexact=name).exists():
                InflowCategory.objects.create(name=name, description=description)
                messages.success(request, f"Inflow Category '{name}' created successfully.")
            else:
                messages.error(request, f"A category named '{name}' already exists.")
        else:
            messages.error(request, "Category name is required.")
    return redirect('dashboard:master_dashboard')

@admin_required
def approve_pin_reset_view(request, pk):
    if request.method == 'POST':
        pin_request = get_object_or_404(PinResetRequest, pk=pk)
        temp_pin = f"{random.randint(1000, 9999)}"
        
        # Reset password
        member = pin_request.member
        member.set_password(temp_pin)
        member.save()

        # Update PIN request
        pin_request.is_resolved = True
        pin_request.temp_pin = temp_pin
        pin_request.resolved_at = timezone.now()
        pin_request.save()

        messages.success(request, f"Successfully reset PIN for {member.name}. Temporary PIN: {temp_pin}")
    return redirect('dashboard:master_dashboard')

@admin_required
def send_announcement_view(request):
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            subscriptions = WebPushSubscription.objects.all()
            sent_count = 0
            
            payload = {
                'title': 'CYON Harvest Broadcast',
                'body': message,
                'url': '/'
            }
            
            for sub in subscriptions:
                if send_web_push(sub, payload):
                    sent_count += 1
                    
            messages.success(request, f'Announcement sent successfully to {sent_count} active devices: "{message}"')
        else:
            messages.error(request, 'Announcement message cannot be empty.')
        return redirect('dashboard:master_dashboard')
    return redirect('dashboard:master_dashboard')

@admin_required
def generate_admin_token_view(request):
    if request.method == 'POST':
        import random
        from django.utils import timezone
        from datetime import timedelta
        from accounts.models import AdminToken
        
        # Generate a 6-digit token
        token_str = f"{random.randint(100000, 999999)}"
        # Valid for 10 minutes
        expires = timezone.now() + timedelta(minutes=10)
        
        AdminToken.objects.create(
            admin=request.user,
            token=token_str,
            expires_at=expires
        )
        
        messages.success(request, f"Generated Override Token: {token_str}. It is valid for 10 minutes.")
        return redirect('dashboard:master_dashboard')
    return redirect('dashboard:master_dashboard')

@admin_required
def record_pledge_view(request):
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')
        category_id = request.POST.get('category_id')
        note = request.POST.get('note')
        
        from contributions.models import Pledge
        from accounts.models import Member
        
        member = Member.objects.get(id=member_id) if member_id else None
        
        # Determine name/phone based on member or external
        if member:
            pledge_name = member.name
            pledge_phone = member.identifier
        else:
            pledge_name = name
            pledge_phone = phone

        category = None
        if category_id:
            category = InflowCategory.objects.get(id=category_id)

        Pledge.objects.create(
            member=member,
            name=pledge_name,
            phone=pledge_phone,
            amount_pledged=amount,
            inflow_category=category,
            note=note,
            status='approved' # Admin created, so instantly approved
        )
        messages.success(request, f"Pledge successfully recorded for {pledge_name}.")
    return redirect('dashboard:master_dashboard')

@admin_required
def approve_pledge_view(request, pk):
    from contributions.models import Pledge
    pledge = get_object_or_404(Pledge, pk=pk)
    if request.method == 'POST':
        pledge.status = 'approved'
        pledge.save()
        messages.success(request, f"Pledge for {pledge.name} approved.")
    return redirect('dashboard:master_dashboard')

@admin_required
def revoke_pledge_view(request, pk):
    from contributions.models import Pledge
    from accounts.models import AdminToken
    pledge = get_object_or_404(Pledge, pk=pk)
    if request.method == 'POST':
        token_str = request.POST.get('override_token')
        
        # Token must be valid, not used, and NOT generated by the current admin
        try:
            token_obj = AdminToken.objects.get(token=token_str, is_used=False)
            if not token_obj.is_valid():
                messages.error(request, "Override Token has expired.")
                return redirect('dashboard:master_dashboard')
            
            if token_obj.admin == request.user:
                messages.error(request, "You cannot use your own Override Token. Another admin must authorize this.")
                return redirect('dashboard:master_dashboard')
            
            # Token is valid and from a different admin!
            token_obj.is_used = True
            token_obj.save()
            
            pledge.status = 'voided'
            pledge.save()
            
            messages.success(request, f"Pledge for {pledge.name} has been successfully revoked (Authorized by {token_obj.admin.name}).")
            
        except AdminToken.DoesNotExist:
            messages.error(request, "Invalid Override Token.")
            
    return redirect('dashboard:master_dashboard')

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

@admin_required
def import_parishioners_view(request):
    from contributions.models import Parishioner
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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import WebPushSubscription
from pywebpush import webpush, WebPushException
import json

@csrf_exempt
def save_push_subscription_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            endpoint = data.get('endpoint')
            keys = data.get('keys', {})
            p256dh = keys.get('p256dh')
            auth = keys.get('auth')
            
            if not endpoint or not p256dh or not auth:
                return JsonResponse({'error': 'Missing subscription parameters'}, status=400)
            
            user = request.user if request.user.is_authenticated else None
            
            subscription, created = WebPushSubscription.objects.update_or_create(
                endpoint=endpoint,
                defaults={
                    'user': user,
                    'p256dh': p256dh,
                    'auth': auth
                }
            )
            return JsonResponse({'status': 'success', 'created': created})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def send_web_push(subscription, payload_data):
    """
    Sends a Web Push notification to a given WebPushSubscription.
    payload_data: dict with 'title', 'body', 'url', etc.
    """
    try:
        vapid_private_key = settings.WEBPUSH_VAPID_PRIVATE_KEY
        vapid_public_key = settings.WEBPUSH_VAPID_PUBLIC_KEY
        vapid_claims = {"sub": settings.WEBPUSH_VAPID_CLAIMS}

        if not vapid_private_key or not vapid_public_key:
            print("VAPID keys not configured.")
            return False

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth
            }
        }

        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload_data),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
            ttl=86400  # 1 day
        )
        return True
    except WebPushException as ex:
        print(f"WebPushException: {ex}")
        if ex.response is not None and ex.response.status_code in [404, 410]:
            subscription.delete()
        return False
    except Exception as e:
        print(f"Error sending web push: {e}")
        return False

def send_approval_push_notification(contribution):
    if contribution.referred_by:
        subscriptions = WebPushSubscription.objects.filter(user=contribution.referred_by)
        payload = {
            'title': 'Contribution Approved! 🎉',
            'body': f'Approved contribution of ₦{contribution.amount:,.2f} from {contribution.name} was added to your profile.',
            'url': '/dashboard/hub/'
        }
        for sub in subscriptions:
            send_web_push(sub, payload)





