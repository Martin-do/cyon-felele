from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Member

def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        pin = request.POST.get('pin')
        user = authenticate(request, username=identifier, password=pin)
        if user is not None:
            login(request, user)
            return redirect('dashboard:member_hub')
        else:
            messages.error(request, 'Invalid Phone/Email or PIN.')
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
            messages.success(request, f'Welcome, {name}! Your account is ready.')
        return redirect('dashboard:member_hub')

    return render(request, 'accounts/signup.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')
