import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
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


class AdminTransactionPagination(PageNumberPagination):
    page_size = 50

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

        if method:
            queryset = queryset.filter(method__icontains=method)
        if status_val:
            queryset = queryset.filter(status=status_val)
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        # Single database aggregation pass using Sum with filter=Q(...) conditional aggregations
        stats = queryset.aggregate(
            total_raised=Sum('amount'),
            cash=Sum('amount', filter=Q(method__icontains='Cash')),
            pos=Sum('amount', filter=Q(method__icontains='POS')),
            transfer=Sum('amount', filter=Q(method__icontains='Transfer')),
            pledges=Sum('amount', filter=Q(method__icontains='Pledge')),
            paystack=Sum('amount', filter=Q(method__icontains='Paystack')),
        )

        total_raised = float(stats['total_raised'] or 0.0)
        cash = float(stats['cash'] or 0.0)
        pos = float(stats['pos'] or 0.0)
        transfer = float(stats['transfer'] or 0.0)
        pledges = float(stats['pledges'] or 0.0)
        paystack = float(stats['paystack'] or 0.0)

        target = 5000000
        progress_percentage = min(int((total_raised / target) * 100), 100) if total_raised > 0 else 0

        statistics = {
            'total_raised': total_raised,
            'cash': cash,
            'pos': pos,
            'transfer': transfer,
            'pledges': pledges,
            'paystack': paystack,
            'progress_percentage': progress_percentage
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

            print(f"NOTIFICATION: Sending approval notice to {contribution.name} at {contribution.phone}.")

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

        url = f"https://api.paystack.co/transaction/verify/{contribution.idempotency_key}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
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

