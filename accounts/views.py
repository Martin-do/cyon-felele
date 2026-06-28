from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.cache import cache
from .models import Member

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        ip = get_client_ip(request)
        cache_key = f"login_attempts_{identifier}_{ip}"
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            messages.error(request, 'Too many failed login attempts. Please try again in 15 minutes.')
            return render(request, 'accounts/login.html')

        pin = request.POST.get('pin')
        user = authenticate(request, username=identifier, password=pin)
        if user is not None:
            cache.delete(cache_key)
            login(request, user)
            return redirect('dashboard:member_hub')
        else:
            cache.set(cache_key, attempts + 1, timeout=900)
            messages.error(request, f'Invalid Phone/Email or PIN. Attempt {attempts + 1} of 5.')
    return render(request, 'accounts/login.html')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:member_hub')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        identifier = request.POST.get('identifier', '').strip()
        pin = request.POST.get('pin', '').strip()
        pin_confirm = request.POST.get('pin_confirm', '').strip()

        # Validate
        if not name or not identifier or not pin:
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/signup.html')

        if len(pin) != 4 or not pin.isdigit():
            messages.error(request, 'PIN must be exactly 4 digits.')
            return render(request, 'accounts/signup.html')

        if pin != pin_confirm:
            messages.error(request, 'PINs do not match.')
            return render(request, 'accounts/signup.html')

        if Member.objects.filter(identifier=identifier).exists():
            messages.error(request, 'An account with that phone/email already exists. Please log in.')
            return render(request, 'accounts/signup.html')

        # Create the member account
        member = Member.objects.create_user(identifier=identifier, password=pin, name=name)

        # Automatically log them in
        user = authenticate(request, username=identifier, password=pin)
        if user:
            login(request, user)
            messages.success(request, f'Welcome, {name}! Please complete your profile.')
        return redirect('accounts:onboarding')

    return render(request, 'accounts/signup.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

from django.contrib.auth.decorators import login_required

@login_required(login_url='/accounts/login/')
def onboarding_view(request):
    user = request.user
    if user.has_completed_onboarding:
        return redirect('dashboard:member_hub')
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        title = request.POST.get('contestant_title')
        gender = request.POST.get('gender')
        
        if first_name or last_name:
            user.name = f"{first_name} {last_name}".strip()
            
        if gender in dict(Member.GENDER_CHOICES):
            user.gender = gender
            user.contestant_title = 'Most Influential Youth Fundraiser'
            
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            
        user.has_completed_onboarding = True
        user.save()
        messages.success(request, 'Onboarding complete! Welcome to your dashboard.')
        return redirect('dashboard:member_hub')
        
    # Pre-fill name if available
    name_parts = user.name.split(' ', 1)
    context = {
        'first_name': name_parts[0] if len(name_parts) > 0 else '',
        'last_name': name_parts[1] if len(name_parts) > 1 else '',
        'titles': Member.TITLE_CHOICES
    }
    return render(request, 'accounts/onboarding.html', context)

from .models import PinResetRequest
from django.core.mail import send_mail

def forgot_pin_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        if not identifier:
            messages.error(request, 'Identifier is required.')
            return render(request, 'accounts/forgot_pin.html')

        ip = get_client_ip(request)
        cache_key = f"forgot_pin_attempts_{identifier}_{ip}"
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            messages.error(request, 'Too many PIN reset requests. Please try again in 15 minutes.')
            return render(request, 'accounts/forgot_pin.html')

        try:
            member = Member.objects.get(identifier=identifier)
        except Member.DoesNotExist:
            cache.set(cache_key, attempts + 1, timeout=900)
            messages.error(request, f'No account found with that phone number or email. Attempt {attempts + 1} of 5.')
            return render(request, 'accounts/forgot_pin.html')

        if '@' in identifier:
            # Token/Email reset path (simulated for simplicity, prints to console/logs)
            import random
            temp_pin = f"{random.randint(1000, 9999)}"
            member.set_password(temp_pin)
            member.save()
            
            # Print to log
            print(f"RESET PIN EMAIL SIMULATION: Sent to {identifier}. New Temporary PIN: {temp_pin}")
            messages.success(request, 'A new temporary 4-digit PIN has been generated and sent to your email.')
            return redirect('accounts:login')
        else:
            # Phone request path
            # Check if there is already a pending request
            existing = PinResetRequest.objects.filter(member=member, is_resolved=False).exists()
            if not existing:
                PinResetRequest.objects.create(member=member)
            messages.success(request, 'PIN reset request submitted! Please notify your Parish Admin or Usher to retrieve your new PIN.')
            return redirect('accounts:login')

    return render(request, 'accounts/forgot_pin.html')

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

@login_required(login_url='/accounts/login/')
def settings_view(request):
    user = request.user
    if request.method == 'POST':
        # Handle PIN change
        old_pin = request.POST.get('old_pin')
        new_pin = request.POST.get('new_pin')
        new_pin_confirm = request.POST.get('new_pin_confirm')
        
        lock_timeout = request.POST.get('lock_timeout')
        
        if lock_timeout:
            try:
                timeout_val = int(lock_timeout)
                if timeout_val in [5, 15, 60]:
                    user.lock_timeout = timeout_val
                    user.save()
                    messages.success(request, 'Lock timeout updated successfully.')
            except ValueError:
                pass
                
        if old_pin and new_pin and new_pin_confirm:
            if not user.check_password(old_pin):
                messages.error(request, 'Incorrect current PIN.')
            elif len(new_pin) != 4 or not new_pin.isdigit():
                messages.error(request, 'New PIN must be exactly 4 digits.')
            elif new_pin != new_pin_confirm:
                messages.error(request, 'New PINs do not match.')
            else:
                user.set_password(new_pin)
                user.save()
                # Re-authenticate to keep session alive
                login(request, user)
                messages.success(request, 'PIN changed successfully.')
                
        if 'profile_picture' in request.FILES or 'custom_flyer' in request.FILES:
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
            if 'custom_flyer' in request.FILES:
                user.custom_flyer = request.FILES['custom_flyer']
            user.save()
            
            # Invalidate cached flyer
            import os
            from django.conf import settings
            cache_path = os.path.join(settings.MEDIA_ROOT, 'flyers', f"{user.id}.png")
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except Exception:
                    pass
                    
            messages.success(request, 'Profile media updated successfully.')
                
        return redirect('accounts:settings')

    return render(request, 'accounts/settings.html', {'user': user})

@login_required(login_url='/accounts/login/')
def verify_pin_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pin = data.get('pin', '')
            if request.user.check_password(pin):
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Incorrect PIN'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid request'})
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

