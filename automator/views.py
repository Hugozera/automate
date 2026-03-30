from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import AutomationLog, ShopifyAccount
from .automator import Automator, discover_cdp_endpoints
import threading
import subprocess
import os
import time
import json
from django.db import connection

automation_thread = None
stop_event = threading.Event()

def index(request):
    return render(request, 'automator/index.html')

def logs(request):
    # Use raw SQL to avoid model fields mismatch if DB schema is out-of-date
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT timestamp, message FROM automator_automationlog ORDER BY timestamp DESC LIMIT 100")
            rows = cur.fetchall()
        items = []
        for ts, msg in rows:
            try:
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                ts_str = str(ts)
            items.append({'timestamp': ts_str, 'message': msg})
        return JsonResponse({'logs': items})
    except Exception as e:
        return JsonResponse({'logs': [], 'error': str(e)})

def accounts(request):
    accounts = ShopifyAccount.objects.all().order_by('-created_at')[:50]
    return JsonResponse({
        'accounts': [{
            'email': account.email,
            'phone': account.phone,
            'created_at': account.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for account in accounts]
    })

def browsers(request):
    endpoints = discover_cdp_endpoints()
    return JsonResponse({'browsers': endpoints})

@csrf_exempt
def start(request):
    global automation_thread, stop_event
    
    if automation_thread and automation_thread.is_alive():
        return JsonResponse({'status': 'already_running'})
    
    stop_event.clear()
    cdp_endpoint = request.GET.get('cdp')
    
    automator = Automator(stop_event, cdp_endpoint)
    automation_thread = threading.Thread(target=automator.run)
    automation_thread.daemon = True
    automation_thread.start()
    
    return JsonResponse({'status': 'started'})

def stop(request):
    global stop_event
    stop_event.set()
    return JsonResponse({'status': 'stopping'})

def status(request):
    global automation_thread
    is_running = automation_thread and automation_thread.is_alive()
    return JsonResponse({'running': is_running})

@csrf_exempt
def start_browser(request):
    port = request.GET.get('port', '9222')
    user_data_dir = request.GET.get('user_data_dir')
    
    if not user_data_dir:
        return JsonResponse({'status': 'error', 'message': 'user_data_dir required'})
    
    try:
        cmd = f'start chrome --remote-debugging-port={port} --user-data-dir="{user_data_dir}"'
        os.system(cmd)
        time.sleep(2)
        return JsonResponse({'status': 'browser_started', 'port': port})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# Backwards-compatible wrappers for original URL names
def start_automation(request):
    return start(request)


def stop_automation(request):
    return stop(request)


def get_logs(request):
    return logs(request)


def get_accounts(request):
    return accounts(request)