import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from accounts.models import Member
from contributions.models import Contribution
from django.contrib import messages
from django.http import HttpResponse

@login_required(login_url='/accounts/login/')
def member_hub_view(request):
    user = request.user
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            title = request.POST.get('contestant_title')
            if title in dict(Member.TITLE_CHOICES):
                user.contestant_title = title
            
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
            
            user.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard:member_hub')

    referred_contributions = Contribution.objects.filter(referred_by=user, is_voided=False, status='approved')
    total_referred = referred_contributions.aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    progress_percentage = 0
    if user.levy_amount > 0:
        progress_percentage = min(int((user.levy_paid / user.levy_amount) * 100), 100)

    base_url = request.build_absolute_uri('/')[:-1] 
    referral_link = f"{base_url}/support/{user.referral_slug}/"

    context = {
        'total_referred': total_referred,
        'recent_referrals': referred_contributions.order_by('-timestamp')[:5],
        'progress_percentage': progress_percentage,
        'referral_link': referral_link,
        'member': user,
    }
    return render(request, 'dashboard/member_hub.html', context)

@login_required(login_url='/accounts/login/')
def generate_flyer_view(request):
    user = request.user
    base_url = request.build_absolute_uri('/')[:-1] 
    referral_link = f"{base_url}/support/{user.referral_slug}/"
    
    context = {
        'member': user,
        'referral_link': referral_link,
        'qr_url': f"{base_url}/dashboard/qr-code/"
    }
    return render(request, 'dashboard/flyer.html', context)

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
    leaderboard = []
    
    for member in members:
        total = Contribution.objects.filter(referred_by=member, is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
        if total > 0:
            leaderboard.append({
                'name': member.name,
                'total': total
            })
            
    leaderboard = sorted(leaderboard, key=lambda x: x['total'], reverse=True)
    
    total_harvest = Contribution.objects.filter(is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    context = {
        'leaderboard': leaderboard,
        'total_harvest': total_harvest
    }
    return render(request, 'dashboard/leaderboard.html', context)

import csv
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required(login_url='/admin/login/')
def master_dashboard_view(request):
    contributions = Contribution.objects.filter(is_voided=False, status='approved').order_by('-timestamp')
    
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if method and method != 'All':
        contributions = contributions.filter(method__icontains=method)
    
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
    progress_percentage = min(int((total_amount / target_amount) * 100), 100) if total_amount else 0

    cash_total = contributions.filter(method__icontains='Cash').aggregate(Sum('amount'))['amount__sum'] or 0.00
    pos_total = contributions.filter(method__icontains='POS').aggregate(Sum('amount'))['amount__sum'] or 0.00
    transfer_total = contributions.filter(method__icontains='Transfer').aggregate(Sum('amount'))['amount__sum'] or 0.00
    pledge_total = contributions.filter(method__icontains='Pledge').aggregate(Sum('amount'))['amount__sum'] or 0.00

    context = {
        'contributions': contributions,
        'total_amount': total_amount,
        'progress_percentage': progress_percentage,
        'cash_total': cash_total,
        'pos_total': pos_total,
        'transfer_total': transfer_total,
        'pledge_total': pledge_total,
        'method': method,
        'date_from': date_from,
        'date_to': date_to,
        'query_string': request.GET.urlencode(),
    }
    return render(request, 'dashboard/admin_master.html', context)

@staff_member_required(login_url='/admin/login/')
def export_csv_view(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="harvest_contributions.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Name', 'Phone', 'Amount', 'Method', 'Source', 'Referred By', 'Anonymous', 'Date'])
    
    contributions = Contribution.objects.filter(is_voided=False, status='approved').order_by('timestamp')
    
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if method and method != 'All':
        contributions = contributions.filter(method__icontains=method)
    
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

@staff_member_required(login_url='/admin/login/')
def approval_center_view(request):
    pending_contributions = Contribution.objects.filter(is_voided=False, status='pending').order_by('-timestamp')
    context = {
        'contributions': pending_contributions,
    }
    return render(request, 'dashboard/approval_center.html', context)

@staff_member_required(login_url='/admin/login/')
def approve_contribution_view(request, pk):
    if request.method == 'POST':
        contribution = get_object_or_404(Contribution, pk=pk)
        contribution.status = 'approved'
        contribution.save()
        
        # Trigger notification (Email/SMS) here
        print(f"NOTIFICATION: Sending approval notice to {contribution.name} at {contribution.phone}.")
        
        messages.success(request, f"Approved contribution from {contribution.name}.")
    return redirect('dashboard:approval_center')

@staff_member_required(login_url='/admin/login/')
def reject_contribution_view(request, pk):
    if request.method == 'POST':
        contribution = get_object_or_404(Contribution, pk=pk)
        contribution.status = 'rejected'
        contribution.save()
        messages.info(request, f"Rejected contribution from {contribution.name}.")
    return redirect('dashboard:approval_center')

@staff_member_required(login_url='/admin/login/')
def live_entry_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        amount = request.POST.get('amount')
        method = request.POST.get('method', 'Cash')
        phone = request.POST.get('phone', '')
        referred_by_id = request.POST.get('referred_by', '')
        
        referrer = None
        if referred_by_id:
            try:
                referrer = Member.objects.get(id=referred_by_id)
            except Member.DoesNotExist:
                pass
                
        Contribution.objects.create(
            name=name,
            amount=amount,
            method=method,
            phone=phone,
            referred_by=referrer,
            source='live_log',
            status='approved',
            recorder_id=request.user.name if request.user.name else request.user.identifier
        )
        messages.success(request, f"Successfully recorded {method} payment from {name}.")
        return redirect('dashboard:live_entry')
        
    members = Member.objects.filter(is_active=True).order_by('name')
    context = {
        'members': members,
    }
    return render(request, 'dashboard/live_entry.html', context)

