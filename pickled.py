#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template_string, send_from_directory, send_file, redirect, session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
import io
from functools import wraps
from datetime import datetime
import time
import os
import glob
import json
import zipfile
import shutil
import csv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import logging
import logging.handlers
from cryptography.fernet import Fernet
import base64
from werkzeug.utils import secure_filename

__version__ = "1.0.2"

app = Flask(__name__)
app.secret_key = 'chiavesegreta1'  # Chiave segreta per le sessioni
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = 'csrfsecretkey123'  # Chiave segreta per CSRF
csrf = CSRFProtect(app)

# Credenziali hardcoded
USERNAME = "jar"
PASSWORD = "cucumber"

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Percorsi dei file
current_dir = os.path.dirname(os.path.abspath(__file__))
SWITCHES_FILE = os.path.join(current_dir, 'switches.json')
SCHEDULES_FILE = os.path.join(current_dir, 'schedules.json')
KEY_FILE = os.path.join(current_dir, 'encryption.key')
LOG_DIR = os.path.join(current_dir, 'logs')
EVENTS_LOG = os.path.join(LOG_DIR, 'events.log')
BACKUP_DIR = os.path.join(current_dir, 'backups')

# Crea le directory necessarie
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Configura il logger per i file
file_handler = logging.handlers.TimedRotatingFileHandler(
    EVENTS_LOG, when='midnight', interval=1, backupCount=12,
    encoding='utf-8', delay=False
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
file_handler.suffix = "%d_%m_%Y.log"
logger.addHandler(file_handler)

# Inizializzazione dello scheduler
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Inizializzazione della crittografia
def get_encryption_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as key_file:
            key_file.write(key)
        return key

fernet = Fernet(get_encryption_key())

def encrypt_password(password):
    if not password:
        return ""
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password):
    if not encrypted_password:
        return ""
    return fernet.decrypt(encrypted_password.encode()).decode()

# Funzioni di persistenza dati
def load_switches():
    try:
        if not os.path.exists(SWITCHES_FILE):
            return []

        with open(SWITCHES_FILE, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
            if not content:
                return []
            
            switches_data = json.loads(content)
            
            # Correzione: garantiamo che enable_password sia sempre valorizzato
            for switch in switches_data:
                if not switch.get('enable_password'):
                    switch['enable_password'] = switch['password']
            
            return switches_data
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in switches file: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error loading switches: {str(e)}")
        return []

def save_switches(switches_data):
    with open(SWITCHES_FILE, 'w') as f:
        json.dump(switches_data, f, indent=4)

def load_schedules():
    try:
        if os.path.exists(SCHEDULES_FILE):
            with open(SCHEDULES_FILE, 'r') as f:
                schedules = json.load(f)
                for schedule in schedules:
                    if schedule.get('enabled', True):
                        add_scheduled_job(schedule)
                return schedules
        return []
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error during schedule update: {str(e)}")
        return []

def save_schedules(schedules_data):
    with open(SCHEDULES_FILE, 'w') as f:
        json.dump(schedules_data, f, indent=4)

# Funzioni per lo scheduling
def add_scheduled_job(schedule):
    trigger = None
    schedule_type = schedule['type']
    time_str = schedule['time']
    hour, minute = map(int, time_str.split(':'))
    
    if schedule_type == 'once':
        run_date = datetime.strptime(schedule['date'], '%Y-%m-%d')
        run_date = run_date.replace(hour=hour, minute=minute)
        trigger = 'date'
        kwargs = {'run_date': run_date}
    elif schedule_type == 'daily':
        trigger = CronTrigger(hour=hour, minute=minute)
    elif schedule_type == 'weekly':
        day_of_week = schedule['day_of_week']
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
    elif schedule_type == 'monthly':
        day = schedule['day']
        trigger = CronTrigger(day=day, hour=hour, minute=minute)
    elif schedule_type == 'yearly':
        month = schedule['month']
        day = schedule['day']
        trigger = CronTrigger(month=month, day=day, hour=hour, minute=minute)
    
    if trigger:
        job_func = execute_scheduled_backup if 'switch_index' in schedule else execute_global_scheduled_backup
        args = [schedule['switch_index']] if 'switch_index' in schedule else []
        
        scheduler.add_job(
            job_func,
            trigger,
            args=args,
            id=schedule['id'],
            name=f"Backup {'switch ' + str(schedule['switch_index']) if 'switch_index' in schedule else 'globale'}",
            replace_existing=True,
            **kwargs if schedule_type == 'once' else {}
        )

def execute_scheduled_backup(switch_index):
    try:
        with app.app_context():
            switches_data = load_switches()
            if 0 <= switch_index < len(switches_data):
                switch = switches_data[switch_index]
                logger.info(f"Esecuzione backup programmato per {switch['hostname']} ({switch['ip']})")
                result = backup_switch({'index': switch_index, 'scheduled': True})
                if not result.get('success', False):
                    logger.error(f"Error during scheduled backup: {result.get('message', 'Nessun dettaglio')}")
    except Exception as e:
        logger.error(f"Error during the execution of the scheduled backup: {str(e)}")

def execute_global_scheduled_backup():
    try:
        with app.app_context():
            logger.info("Global backup execution set for all devices")
            switches_data = load_switches()
            for i in range(len(switches_data)):
                execute_scheduled_backup(i)
    except Exception as e:
        logger.error(f"Error during the global backup execution: {str(e)}")

# Funzioni di utilità
def is_logged_in():
    return session.get('logged_in')

def login_required(f):
    @wraps(f)  # Importa wraps da functools
    @csrf.exempt
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def get_schedule_description(schedule):
    desc = ''
    time_str = schedule.get('time', '00:00')
    
    if schedule['type'] == 'once':
        desc = f"Una volta il {schedule['date']} alle {time_str}"
    elif schedule['type'] == 'daily':
        desc = f"Giornaliero alle {time_str}"
    elif schedule['type'] == 'weekly':
        days = ['Domenica', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato']
        day = int(schedule['day_of_week'])
        desc = f"Settimanale ogni {days[day]} alle {time_str}"
    elif schedule['type'] == 'monthly':
        desc = f"Mensile il giorno {schedule['day']} alle {time_str}"
    elif schedule['type'] == 'yearly':
        months = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                 'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        month = int(schedule['month']) - 1
        desc = f"Annuale il {schedule['day']} {months[month]} alle {time_str}"
    
    return desc

@app.after_request
def set_csrf_cookie(response):
    response.set_cookie('csrf_token', generate_csrf())
    return response

# Route per l'autenticazione
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == USERNAME and request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect('/')
        return '''
            <script>
                alert("Credenziali errate!");
                window.location.href = "/login";
            </script>
        '''

    csrf_token = generate_csrf()  # genera token da inserire nel form

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PICKLED - Login</title>
        <style>
            body {{ font-family: Arial; text-align: center; margin-top: 50px; }}
            input {{ padding: 8px; margin: 5px; width: 200px; }}
            button {{ padding: 10px 20px; background: #4CAF50; color: white; border: none; }}
        </style>
    </head>
    <body>
        <h2>PICKLED – Platform for Instant Config Keep & Lightweight Export Daemon</h2> <br/> <h3>Login</h3>
        <form method="post" action="/login">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            <div><input type="text" name="username" placeholder="Username" required></div>
            <div><input type="password" name="password" placeholder="Password" required></div>
            <button type="submit">Accedi</button>
        </form>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/')
@login_required
def index():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template_string(HTML_TEMPLATE, current_date=current_date)

def csrf_exempt_login_required(f):
    return csrf.exempt(login_required(f))

# API per la gestione degli switch
@app.route('/add_switch', methods=['POST'])
@login_required
def add_switch():
    data = request.get_json()
    if not all(key in data for key in ['hostname', 'ip', 'username', 'password']):
        return jsonify({'success': False, 'message': 'Missing data'})
    
    # Encrypt passwords
    encrypted_password = encrypt_password(data['password'])
    # Garantiamo che enable_password sia sempre uguale a password se non specificato
    encrypted_enable = encrypt_password(data.get('enable_password', data['password']))
    
    switch_data = {
        'hostname': data['hostname'],
        'ip': data['ip'],
        'username': data['username'],
        'password': encrypted_password,
        'enable_password': encrypted_enable,  # Questo campo non sarà mai vuoto
        'device_type': data.get('device_type', 'cisco_ios')
    }
    
    switches_data = load_switches()
    switches_data.append(switch_data)
    save_switches(switches_data)
    
    logger.info(f"Added switch: {data['hostname']} ({data['ip']})")
    return jsonify({'success': True, 'message': 'Switch added successfully'})

@app.route('/get_switches', methods=['GET'])
@login_required
def get_switches_api():
    switches_data = load_switches()
    return jsonify(switches_data)

@app.route('/update_switch', methods=['POST'])
@login_required
def update_switch():
    data = request.get_json()
    if 'index' not in data:
        return jsonify({'success': False, 'message': 'Indice mancante'})
    
    switches_data = load_switches()
    index = int(data['index'])
    
    if 0 <= index < len(switches_data):
        old_hostname = switches_data[index]['hostname']
        
        # Keep existing passwords if not provided, otherwise encrypt new ones
        password = encrypt_password(data['password']) if 'password' in data and data['password'] else switches_data[index]['password']
        # For enable_password, use the new password if provided, otherwise keep existing enable_password
        enable_password = encrypt_password(data['enable_password']) if 'enable_password' in data and data['enable_password'] else password
        
        switches_data[index] = {
            'hostname': data['hostname'],
            'ip': data['ip'],
            'username': data['username'],
            'password': password,
            'enable_password': enable_password,
            'device_type': data.get('device_type', switches_data[index].get('device_type', 'cisco_ios'))
        }
        
        save_switches(switches_data)
        logger.info(f"Aggiornato switch: da {old_hostname} a {data['hostname']} ({data['ip']})")
        return jsonify({'success': True, 'message': 'Switch aggiornato'})
    else:
        return jsonify({'success': False, 'message': 'Indice non valido'})

@app.route('/delete_switch', methods=['POST'])
@login_required
def delete_switch():
    data = request.get_json()
    if 'index' not in data:
        return jsonify({'success': False, 'message': 'Indice mancante'})
    
    switches_data = load_switches()
    index = int(data['index'])
    
    if 0 <= index < len(switches_data):
        deleted_switch = switches_data.pop(index)
        save_switches(switches_data)
        
        schedules_data = load_schedules()
        schedules_data = [s for s in schedules_data if s.get('switch_index') != index]
        save_schedules(schedules_data)
        
        logger.info(f"Eliminato switch: {deleted_switch['hostname']} ({deleted_switch['ip']})")
        return jsonify({'success': True, 'message': 'Switch eliminato'})
    else:
        return jsonify({'success': False, 'message': 'Indice switch non valido'})

# API per la gestione dei backup
@app.route('/backup_switch', methods=['POST'])
@login_required
def backup_switch_http():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data'})
            
        result = backup_switch(data)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in backup_switch_http: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error_type': 'ServerError'
        }), 500
        
def backup_switch(params):
    logger.debug(f"Starting backup with params: {params}")
    
    try:
        # Parameter validation
        index = params.get('index')
        if index is None:
            error_msg = "Backup failed: Missing index parameter"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

        switches_data = load_switches()
        if not isinstance(switches_data, list):
            error_msg = "Invalid switches data format"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

        if index < 0 or index >= len(switches_data):
            error_msg = f"Backup failed: Invalid switch index {index}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

        # Device information extraction
        switch = switches_data[index]
        hostname = switch['hostname']
        ip = switch['ip']
        username = switch['username']
        password = decrypt_password(switch['password'])
        enable_password = decrypt_password(switch['enable_password'])
        device_type = switch.get('device_type', 'cisco_ios')
        custom_command = switch.get('backup_command')  # Custom backup command if specified

        # Device connection parameters
        device = {
            'device_type': device_type,
            'host': ip,
            'username': username,
            'password': password,
            'secret': enable_password,
            'timeout': 150,  # Increased to 150 seconds
            'session_timeout': 150,
            'global_delay_factor': 3,
            'fast_cli': False,
            'allow_auto_change': True,  # Allow automatic adjustment of connection parameters
            'verbose': False
        }

        logger.debug(f"[{hostname}] Connection parameters: { {k:v for k,v in device.items() if k not in ['password', 'secret']} }")

        # Backup file preparation
        switch_folder = os.path.join(BACKUP_DIR, secure_filename(hostname))
        os.makedirs(switch_folder, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{hostname}_config_{timestamp}.txt"
        backup_path = os.path.join(switch_folder, backup_filename)

        # Comprehensive command list to try
        command_list = [
            custom_command,  # Try custom command first if specified
            'show running-config',
            '\nshow running-config',
            'show startup-config',
            'show config',
            'show configuration',
            'show current-configuration',
            'show full-configuration',
            'more system:running-config',
            'show tech-support | begin Running configuration',
            'terminal length 0\nshow running-config',
            'enable\nshow running-config'
        ]

        # Remove any None values (if custom_command not specified)
        try:
            with ConnectHandler(**device) as net_connect:
                logger.info(f"[{hostname}] Connected successfully, starting advanced backup procedure")

                # Enter enable mode if needed
                try:
                    net_connect.enable()
                    logger.info(f"[{hostname}] Entered enable mode successfully")
                except Exception as e:
                    logger.warning(f"[{hostname}] Enable mode not required: {str(e)}")

                # Start interactive shell session
                net_connect.write_channel('\n')  # Send initial return
                time.sleep(1)
                initial_prompt = net_connect.read_channel()
                logger.debug(f"[{hostname}] Initial prompt: {initial_prompt}")

                # Send pagination disable commands
                pagination_commands = [
                    'terminal length 0\n',
                    'terminal width 512\n',
                    'set cli screen-length 0\n'
                ]

                for cmd in pagination_commands:
                    net_connect.write_channel(cmd)
                    time.sleep(2)
                    output = net_connect.read_channel()
                    logger.debug(f"[{hostname}] Pagination command response: {output}")

                # Start configuration capture
                config_commands = [
                    'show running-config\n',
                    'show running-config all\n',
                    'show tech-support | begin Running configuration\n'
                ]

                full_output = ""
                for cmd in config_commands:
                    logger.info(f"[{hostname}] Sending command: {cmd.strip()}")
                    net_connect.write_channel(cmd)
                    
                    # Progressive output collection
                    start_time = time.time()
                    while time.time() - start_time < 60:  # 60 second timeout per command
                        time.sleep(3)
                        new_data = net_connect.read_channel()
                        if new_data:
                            full_output += new_data
                            logger.debug(f"[{hostname}] Received {len(new_data)} bytes")
                            
                            # Check for termination patterns
                            if any(pattern in new_data for pattern in ['#', 'end', '--More--']):
                                if '--More--' in new_data:
                                    net_connect.write_channel(' ')  # Send space for more
                                break
                        else:
                            break

                # Final cleanup and prompt exit
                net_connect.write_channel('exit\n')
                time.sleep(1)
                net_connect.read_channel()

                # Validate captured output
                if len(full_output.splitlines()) < 20:
                    raise Exception("Insufficient configuration data captured")

                # Clean and save configuration
                clean_output = "\n".join(
                    line for line in full_output.splitlines() 
                    if not any(line.startswith(cmd) for cmd in ['show', 'terminal', 'enable', 'conf t', 'exit'])
                )
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(clean_output)

                logger.info(f"[{hostname}] Backup completed successfully with interactive capture")
                return {
                    'success': True,
                    'message': "Backup completed with interactive capture",
                    'hostname': hostname,
                    'ip': ip,
                    'filename': backup_filename
                }

        except Exception as e:
            logger.error(f"[{hostname}] Interactive capture failed: {str(e)}")
            raise  # Fall through to next attempt

        # If interactive capture fails, try last-resort method
        logger.warning(f"[{hostname}] Trying last-resort backup method")
        try:
            with ConnectHandler(**device) as net_connect:
                # Ultra-simple approach for problematic devices
                output = net_connect.send_command_timing('show running-config', delay_factor=5, max_loops=3000)
                
                if not output or len(output.splitlines()) < 10:
                    raise Exception("Insufficient output")
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(output)

                logger.info(f"[{hostname}] Backup completed with last-resort method")
                return {
                    'success': True,
                    'message': "Backup completed with last-resort method",
                    'hostname': hostname,
                    'ip': ip,
                    'filename': backup_filename
                }

        except Exception as e:
            logger.error(f"[{hostname}] Last-resort method failed: {str(e)}")
            raise

    except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
        error_msg = f"Connection error to {hostname} ({ip}): {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'message': error_msg,
            'hostname': hostname,
            'ip': ip,
            'error_type': type(e).__name__
        }

    except Exception as e:
        error_msg = f"All backup methods failed for {hostname} ({ip}): {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'message': error_msg,
            'hostname': hostname,
            'ip': ip,
            'error_type': 'AllMethodsFailed'
        }

@app.route('/backup_all_switches', methods=['POST'])
@login_required
def backup_all_switches():
    try:
        logger.info("Starting backup process for all devices")
        
        # Carica gli switch con controllo errori rinforzato
        try:
            switches_data = load_switches()
            if not isinstance(switches_data, list):
                error_msg = "Invalid switches data format"
                logger.error(error_msg)
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'count': 0,
                    'total': 0,
                    'results': []
                })
        except Exception as e:
            error_msg = f"Failed to load switches: {str(e)}"
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'message': error_msg,
                'count': 0,
                'total': 0,
                'results': []
            })

        if not switches_data:
            logger.warning("No devices configured for backup")
            return jsonify({
                'success': False,
                'message': 'No devices configured',
                'count': 0,
                'total': 0,
                'results': []
            })

        results = []
        for i, switch in enumerate(switches_data, 1):
            progress_msg = f"Processing device {i}/{len(switches_data)}: {switch['hostname']}"
            logger.info(progress_msg)
            
            result = backup_switch({'index': i-1})
            results.append({
                'success': result.get('success', False),
                'hostname': switch['hostname'],
                'ip': switch['ip'],
                'message': result.get('message', ''),
                'filename': result.get('filename', '')
            })

        success_count = sum(1 for r in results if r['success'])
        completion_msg = f"Backup completed. Success: {success_count}/{len(switches_data)}"
        logger.info(completion_msg)
        
        return jsonify({
            'success': True,
            'count': success_count,
            'total': len(switches_data),
            'results': results
        })

    except Exception as e:
        error_msg = f"Unexpected error in backup_all_switches: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'message': error_msg,
            'count': 0,
            'total': 0,
            'results': []
        }), 500

@app.route('/get_switch_backups', methods=['POST'])
@login_required
def get_switch_backups():
    data = request.get_json()
    if 'index' not in data:
        return jsonify({'success': False, 'message': 'Indice mancante'})
    
    switches_data = load_switches()
    index = int(data['index'])
    
    if index < 0 or index >= len(switches_data):
        return jsonify({'success': False, 'message': 'Indice switch non valido'})
    
    switch = switches_data[index]
    hostname = switch['hostname']
    switch_folder = os.path.join(BACKUP_DIR, secure_filename(hostname))
    
    if not os.path.exists(switch_folder):
        return jsonify({'success': True, 'hostname': hostname, 'backups': []})
    
    backups = []
    for filename in sorted(os.listdir(switch_folder), reverse=True):
        if filename.endswith('.txt'):
            filepath = os.path.join(switch_folder, filename)
            backups.append({
                'filename': filename,
                'path': filepath
            })
    
    return jsonify({
        'success': True,
        'hostname': hostname,
        'backups': backups
    })

@app.route('/get_backup_content', methods=['POST'])
@login_required
def get_backup_content():
    data = request.get_json()
    if 'filepath' not in data:
        return jsonify({'success': False, 'message': 'Percorso file mancante'})
    
    filepath = data['filepath']
    if not os.path.abspath(filepath).startswith(os.path.abspath(BACKUP_DIR)):
        return jsonify({'success': False, 'message': 'Percorso non valido'})
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'filename': os.path.basename(filepath),
            'content': content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# API per la gestione degli schedule
@app.route('/add_schedule', methods=['POST'])
@login_required
def add_schedule():
    data = request.get_json()
    if not all(key in data for key in ['type', 'time']):
        return jsonify({'success': False, 'message': 'Dati mancanti'})
    
    schedule_id = f"sch_{int(time.time())}_{len(load_schedules())}"
    data['id'] = schedule_id
    data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    schedules_data = load_schedules()
    schedules_data.append(data)
    save_schedules(schedules_data)
    add_scheduled_job(data)
    
    logger.info(f"Aggiunta nuova pianificazione: {get_schedule_description(data)}")
    return jsonify({
        'success': True,
        'message': 'Pianificazione aggiunta',
        'id': schedule_id
    })

@app.route('/get_schedules', methods=['GET'])
@login_required
def get_schedules():
    schedules_data = load_schedules()
    jobs = scheduler.get_jobs()
    
    for schedule in schedules_data:
        job = next((j for j in jobs if j.id == schedule['id']), None)
        if job:
            schedule['next_run'] = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "N/A"
            schedule['enabled'] = True
        else:
            schedule['next_run'] = "N/A"
            schedule['enabled'] = False
    
    return jsonify(schedules_data)

@app.route('/toggle_schedule', methods=['POST'])
@login_required
def toggle_schedule():
    data = request.get_json()
    if not all(key in data for key in ['id', 'enabled']):
        return jsonify({'success': False, 'message': 'Dati mancanti'})
    
    schedules_data = load_schedules()
    schedule = next((s for s in schedules_data if s['id'] == data['id']), None)
    
    if not schedule:
        return jsonify({'success': False, 'message': 'Pianificazione non trovata'})
    
    if data['enabled']:
        add_scheduled_job(schedule)
        schedule['enabled'] = True
        message = 'Pianificazione attivata'
    else:
        scheduler.remove_job(data['id'])
        schedule['enabled'] = False
        message = 'Pianificazione disattivata'
    
    save_schedules(schedules_data)
    logger.info(f"Pianificazione {data['id']} {'attivata' if data['enabled'] else 'disattivata'}")
    return jsonify({'success': True, 'message': message})

@app.route('/delete_schedule', methods=['POST'])
@login_required
def delete_schedule():
    data = request.get_json()
    if 'id' not in data:
        return jsonify({'success': False, 'message': 'ID mancante'})
    
    schedules_data = load_schedules()
    schedule = next((s for s in schedules_data if s['id'] == data['id']), None)
    
    if not schedule:
        return jsonify({'success': False, 'message': 'Pianificazione non trovata'})
    
    scheduler.remove_job(data['id'])
    schedules_data = [s for s in schedules_data if s['id'] != data['id']]
    save_schedules(schedules_data)
    
    logger.info(f"Eliminata pianificazione: {get_schedule_description(schedule)}")
    return jsonify({'success': True, 'message': 'Pianificazione eliminata'})

# API per la gestione dei log
@app.route('/log_event', methods=['POST'])
@login_required
def log_event():
    data = request.get_json()
    if 'message' in data:
        logger.info(data['message'])
    return jsonify({'success': True})

@app.route('/get_full_log', methods=['GET'])
@login_required
def get_full_log():
    try:
        log_content = ""
        if os.path.exists(EVENTS_LOG):
            with open(EVENTS_LOG, 'r') as f:
                log_content = f.read()
        
        archived_logs = []
        if os.path.exists(LOG_DIR):
            for filename in sorted(os.listdir(LOG_DIR), reverse=True):
                if filename.startswith('events.') and filename.endswith('.log') and filename != 'events.log':
                    with open(os.path.join(LOG_DIR, filename), 'r') as f:
                        archived_logs.append(f"=== Log {filename} ===\n{f.read()}\n")
        
        full_log = log_content + "\n" + "\n".join(archived_logs)
        return jsonify({'success': True, 'log': full_log})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# API per l'import/export CSV
@app.route('/upload_csv', methods=['POST'])
@login_required
def upload_csv():
    if 'csv_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'})
    
    csv_file = request.files['csv_file']
    if csv_file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not csv_file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': 'File must be .csv'})
    
    try:
        stream = io.StringIO(csv_file.stream.read().decode('UTF-8'))
        csv_reader = csv.DictReader(stream)
        
        switches_data = load_switches()
        added = 0
        skipped = 0
        existing_ips = {sw['ip'] for sw in switches_data}
        
        for row in csv_reader:
            if not all(field in row for field in ['hostname', 'ip', 'username', 'password']):
                return jsonify({'success': False, 'message': 'CSV format not valid'})
            
            if row['ip'] in existing_ips:
                skipped += 1
                continue
            
            # Always set enable_password equal to password if not provided in CSV
            encrypted_password = encrypt_password(row['password'])
            encrypted_enable_password = encrypt_password(row.get('enable_password', row['password']))
            
            switches_data.append({
                'hostname': row['hostname'],
                'ip': row['ip'],
                'username': row['username'],
                'password': encrypted_password,
                'enable_password': encrypted_enable_password,
                'device_type': row.get('device_type', 'cisco_ios')
            })
            existing_ips.add(row['ip'])
            added += 1
        
        if added > 0:
            save_switches(switches_data)
            logger.info(f"Loaded {added} devices from CSV, {skipped} already present")
        
        return jsonify({
            'success': True,
            'message': 'CSV loaded successfully',
            'added': added,
            'skipped': skipped
        })
    except Exception as e:
        logger.error(f"Error while loading CSV: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
        
@app.route('/export_switches_csv', methods=['GET'])
@login_required
def export_switches_csv():
    try:
        switches_data = load_switches()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['hostname', 'ip', 'username'])
        
        for switch in switches_data:
            writer.writerow([switch['hostname'], switch['ip'], switch['username']])
        
        output.seek(0)
        mem_file = io.BytesIO()
        mem_file.write(output.getvalue().encode('utf-8'))
        mem_file.seek(0)
        
        logger.info(f"Exported {len(switches_data)} devices in CSV")
        return send_file(
            mem_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'switches_backup_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error during the export of CSV: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# HTML Template (rimasto invariato)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PICKLED – Because broken routers don’t explain themselves</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css">
    <style>
        :root {
            --primary-color: #3498db;
            --primary-hover: #2980b9;
            --success-color: #2ecc71;
            --success-hover: #27ae60;
            --danger-color: #e74c3c;
            --danger-hover: #c0392b;
            --warning-color: #f39c12;
            --warning-hover: #e67e22;
            --purple-color: #9b59b6;
            --purple-hover: #8e44ad;
            --dark-color: #2c3e50;
            --light-color: #ecf0f1;
            --gray-light: #f5f5f5;
            --gray-medium: #ddd;
            --gray-dark: #333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--gray-dark);
            margin: 0;
            padding: 0;
            background-color: var(--gray-light);
        }
    .log {
        margin-top: 30px;
        max-height: 300px;
        overflow-y: auto;
        background-color: #1a1a1a;
        color: #e0e0e0;
        padding: 15px;
        border-radius: 4px;
        font-family: monospace;
        white-space: pre-wrap;
        font-size: 14px;
        line-height: 1.5;
    }
    .log div {
        margin-bottom: 5px;
        padding: 3px 5px;
        border-radius: 3px;
    }
    .log div:hover {
        background-color: #2a2a2a;
    }
        .app-container {
            display: flex;
            min-height: 100vh;
            max-width: 1400px;
            margin: 0 auto;
        }
        .left-panel {
            width: 300px;
            background-color: white;
            padding: 20px 15px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .left-panel > button {
            width: calc(100% - 24px);
            padding: 12px;
            margin-top: 5px;
        }
        .right-panel {
            flex: 1;
            padding: 20px;
            background-color: white;
            margin-left: 20px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: var(--dark-color);
            text-align: center;
            margin-bottom: 30px;
        }
        h2 {
            color: var(--dark-color);
            border-bottom: 2px solid var(--primary-color);
            padding-bottom: 8px;
            margin-top: 0;
        }
        .form-group input {
            width: calc(100% - 24px);
            padding: 10px 12px;
            border: 1px solid var(--gray-medium);
            border-radius: 6px;
            font-size: 16px;
            transition: border-color 0.3s, box-shadow 0.3s;
        }
        .form-group input:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
            outline: none;
        }
        .form-group {
            margin-bottom: 18px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--dark-color);
            font-size: 14px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
        }
        input {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--gray-medium);
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: var(--primary-hover);
        }
        .status-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            max-width: 400px;
        }
        .status {
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 10px;
            display: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .log {
            margin-top: 30px;
            max-height: 300px;
            overflow-y: auto;
            background-color: var(--dark-color);
            color: var(--light-color);
            padding: 15px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
        }
	.switch-table {
	    width: 100%;
	    border-collapse: separate;  /* Cambiato da collapse a separate */
	    border-spacing: 0;
	    margin-top: 20px;
	    border-radius: 8px;  /* Aggiunto per smussare gli angoli */
	    overflow: hidden;  /* Per mantenere i bordi arrotondati */
	    box-shadow: 0 2px 10px rgba(0,0,0,0.1);  /* Aggiunto ombreggiatura per migliorare l'aspetto */
	}
        .switch-table th, .switch-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--gray-medium);
        }
        .switch-table th {
            background-color: var(--primary-color);
            color: white;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
        }
        .switch-table th:hover {
            background-color: var(--primary-hover);
        }
        .switch-table tr:hover {
            background-color: var(--gray-light);
        }
        .action-btn {
            padding: 6px 10px;
            margin: 0 2px;
            font-size: 14px;
            min-width: 30px;
        }
        .edit-btn {
            background-color: var(--warning-color);
        }
        .edit-btn:hover {
            background-color: var(--warning-hover);
        }
        .delete-btn {
            background-color: var(--danger-color);
        }
        .delete-btn:hover {
            background-color: var(--danger-hover);
        }
        .backup-btn {
            background-color: var(--success-color);
        }
        .backup-btn:hover {
            background-color: var(--success-hover);
        }
        .view-btn {
            background-color: var(--purple-color);
        }
        .view-btn:hover {
            background-color: var(--purple-hover);
        }
        .backup-all-btn {
            background-color: var(--purple-color);
            margin-top: 20px;
            width: 100%;
        }
        .backup-all-btn:hover {
            background-color: var(--purple-hover);
        }
        .csv-btn {
            background-color: var(--dark-color);
            margin-top: 10px;
            width: 100%;
        }
        .csv-btn:hover {
            background-color: #1a252f;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 8px;
            width: 80%;
            max-width: 900px;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-title {
            font-size: 1.5em;
            font-weight: bold;
        }
        .close-btn {
            font-size: 1.5em;
            cursor: pointer;
        }
        .modal-body {
            flex-grow: 1;
            overflow: auto;
            display: flex;
        }
        .backup-list {
            width: 30%;
            padding-right: 15px;
            border-right: 1px solid var(--gray-medium);
            overflow-y: auto;
        }
        .backup-content {
            width: 70%;
            padding-left: 15px;
            overflow-y: auto;
        }
        .backup-item {
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 4px;
            cursor: pointer;
        }
        .backup-item:hover {
            background-color: var(--gray-light);
        }
        .backup-item.active {
            background-color: var(--primary-color);
            color: white;
        }
        .config-content {
            font-family: monospace;
            white-space: pre;
            background-color: #f8f8f8;
            padding: 10px;
            border-radius: 4px;
            max-height: 60vh;
            overflow-y: auto;
        }
        .split-view {
            display: flex;
            width: 100%;
        }
        .form-column {
            flex: 1;
            padding: 0 10px;
        }
        .log-modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 8px;
            width: 80%;
            max-width: 900px;
            max-height: 80vh;
        }
        .log-content {
            font-family: monospace;
            white-space: pre-wrap;
            background-color: #f8f8f8;
            padding: 15px;
            border-radius: 4px;
            max-height: 60vh;
            overflow-y: auto;
        }
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        ::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        .file-input-container {
            margin-top: 15px;
        }
        .file-input-label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .file-input {
            width: calc(100% - 24px);
            padding: 8px 12px;
        }
        /* Stili per lo scheduling */
        .schedule-section {
            margin-top: 30px;
            border-top: 1px solid var(--gray-medium);
            padding-top: 20px;
        }
        .schedule-form {
            background-color: var(--gray-light);
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 15px;
        }
        .schedule-form h3 {
            margin-top: 0;
            color: var(--dark-color);
            border-bottom: 1px solid var(--gray-medium);
            padding-bottom: 8px;
        }
        .schedule-option {
            display: none;
            margin-top: 10px;
        }
        .schedule-option.active {
            display: block;
        }
        .schedule-list {
            margin-top: 15px;
        }
        .schedule-item {
            padding: 10px;
            background-color: white;
            border: 1px solid var(--gray-medium);
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .schedule-item-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
        }
        .schedule-item-actions {
            display: flex;
            gap: 5px;
        }
        .schedule-item-actions button {
            padding: 2px 6px;
            font-size: 12px;
        }
        .select2-container {
            width: 100% !important;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="status-container">
        <div id="status-message" class="status"></div>
    </div>
    <div class="app-container">
        <!-- Pannello sinistro - Form aggiunta switch -->
        <div class="left-panel">
            <h2>Add device</h2>
            <div class="form-group">
                <label for="hostname">Hostname:</label>
                <input type="text" id="hostname" placeholder="Es: Switch1">
            </div>
            <div class="form-group">
                <label for="ip">IP Address:</label>
                <input type="text" id="ip" placeholder="Es: 192.168.1.1">
            </div>
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" placeholder="Username SSH">
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" placeholder="Password SSH">
            </div>
    	    <div class="form-group">
	        <label for="enable-password">Enable Password (optional):</label>
	        <input type="password" id="enable-password" placeholder="Enable/Secret password">
	    </div>
            <div class="form-group">
	    <label for="device-type">Tipo dispositivo:</label>
	    <select id="device-type" class="form-control">
		<option value="cisco_ios">Cisco IOS</option>
		<option value="cisco_xe">Cisco IOS-XE</option>
		<option value="cisco_xr">Cisco IOS-XR</option>
		<option value="huawei">Huawei</option>
		<option value="juniper">Juniper JunOS</option>
	    </select>
	    </div>
            <button onclick="addSwitch()">Add Switch</button>
            
            <h2 style="margin-top: 30px;">Load CSV</h2>
            <div class="file-input-container">
                <label class="file-input-label" for="csv-file">Select CSV file:</label>
                <input type="file" id="csv-file" class="file-input" accept=".csv">
            </div>
            <button class="csv-btn" onclick="uploadCSV()">
                <i class="fas fa-file-import"></i> Load CSV
            </button>

            <!-- Sezione Pianificazione Backup -->
            <div class="schedule-section">
                <h2>Backup Scheduler</h2>
                
                <div class="schedule-form">
                    <h3>New Schedule</h3>
                    
                    <div class="form-group">
                        <label for="schedule-type">Type:</label>
                        <select id="schedule-type" class="form-control" onchange="showScheduleOptions()">
                            <!--<option value="once">One Time</option>-->
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                            <option value="yearly">Yearly</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="schedule-time">Hour:</label>
                        <input type="time" id="schedule-time" class="form-control" value="00:00">
                    </div>
                    
                    <!-- Opzioni specifiche per tipo -->
                    <div id="once-option" class="schedule-option">
                        <div class="form-group">
                            <label for="schedule-date">Data:</label>
                            <input type="date" id="schedule-date" class="form-control">
                        </div>
                    </div>
                    
                    <div id="weekly-option" class="schedule-option">
                        <div class="form-group">
                            <label for="schedule-day-week">Giorno settimana:</label>
                            <select id="schedule-day-week" class="form-control">
                                <option value="0">Monday</option>
                                <option value="1">Tuesday</option>
                                <option value="2">Wednesday</option>
                                <option value="3">Thursday</option>
                                <option value="4">Friday</option>
                                <option value="5">Saturday</option>
                                <option value="6">Sunday</option>
                            </select>
                        </div>
                    </div>
                    
                    <div id="monthly-option" class="schedule-option">
                        <div class="form-group">
                            <label for="schedule-day-month">Day month:</label>
                            <input type="number" id="schedule-day-month" min="1" max="31" value="1" class="form-control">
                        </div>
                    </div>
                    
                    <div id="yearly-option" class="schedule-option">
                        <div class="form-group">
                            <label for="schedule-month">Month:</label>
                            <select id="schedule-month" class="form-control">
                                <option value="1">January</option>
                                <option value="2">February</option>
                                <option value="3">March</option>
                                <option value="4">April</option>
                                <option value="5">May</option>
                                <option value="6">June</option>
                                <option value="7">July</option>
                                <option value="8">August</option>
                                <option value="9">September</option>
                                <option value="10">October</option>
                                <option value="11">November</option>
                                <option value="12">December</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="schedule-day-year">Day:</label>
                            <input type="number" id="schedule-day-year" min="1" max="31" value="1" class="form-control">
                        </div>
                    </div>
                    
                    <button onclick="addSchedule()" class="backup-btn">
                        <i class="fas fa-calendar-plus"></i> Add Schedule
                    </button>
                </div>
                
                <div class="schedule-list" id="schedules-list">
                    <!-- Lista delle pianificazioni verrà popolata dinamicamente -->
                </div>
            </div>

            <div id="status-message" class="status"></div>

            <h2 style="margin-top: 30px;">Activity Log</h2>
            <div id="log" class="log">Ready to backup...</div>
            <button onclick="viewFullLog()" style="margin-top: 10px; width: 100%;">
                <i class="fas fa-scroll"></i> Show log
            </button>
        </div>

        <!-- Pannello destro - Lista switch -->
        <div class="right-panel">
           <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Device list</h2>
            <div>
             <button onclick="exportSwitchesToCSV()" style="margin-left: 10px;">
                 <i class="fas fa-file-export"></i> Export CSV
             </button>
            <button onclick="window.location.href='/logout'" style="background: #e74c3c;">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
           </div>
          </div>
            <table class="switch-table">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">Hostname <i class="fas fa-sort"></i></th>
                        <th onclick="sortTable(1)">IP <i class="fas fa-sort"></i></th>
                        <th onclick="sortTable(2)">Username <i class="fas fa-sort"></i></th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="switches-table-body">
                    <!-- Le righe della tabella verranno aggiunte qui dinamicamente -->
                </tbody>
            </table>
            <button class="backup-all-btn" onclick="backupAllSwitches()">
                <i class="fas fa-download"></i> Backup all devices
            </button>
        </div>
    </div>

    <!-- Modal per visualizzare i backup -->
    <div id="backup-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Avalaible backup by <span id="modal-switch-name"></span></div>
                <span class="close-btn" onclick="closeModal()">&times;</span>
            </div>
            <div class="modal-body">
                <div class="backup-list" id="backup-list">
                    <!-- Lista dei backup -->
                </div>
                <div class="backup-content">
                    <div id="backup-content-placeholder">Select a backup from the list to view content</div>
                    <div id="backup-content" class="config-content" style="display: none;"></div>
                </div>
            </div>
        </div>
    </div>

	<!-- Modal per modificare switch -->
	<div id="edit-modal" class="modal">
	    <div class="modal-content" style="max-width: 600px;">
		<div class="modal-header">
		    <div class="modal-title">Modify Device</div>
		    <span class="close-btn" onclick="closeEditModal()">&times;</span>
		</div>
		<div class="modal-body">
		    <div class="split-view">
		        <div class="form-column">
		            <div class="form-group">
		                <label for="edit-hostname">Hostname:</label>
		                <input type="text" id="edit-hostname">
		            </div>
		            <div class="form-group">
		                <label for="edit-ip">IP Address:</label>
		                <input type="text" id="edit-ip">
		            </div>
		        </div>
		        <div class="form-column">
		            <div class="form-group">
		                <label for="edit-username">Username:</label>
		                <input type="text" id="edit-username">
		            </div>
		            <div class="form-group">
		                <label for="edit-password">Password:</label>
		                <input type="password" id="edit-password" placeholder="Leave blank to keep current">
		            </div>
		            <div class="form-group">
		                <label for="edit-enable-password">Enable Password:</label>
		                <input type="password" id="edit-enable-password" placeholder="Leave blank to keep current">
		            </div>
		        </div>
		    </div>
		</div>
		<div style="text-align: right; margin-top: 20px;">
		    <button onclick="closeEditModal()">Cancel</button>
		    <button class="backup-btn" onclick="saveEditedSwitch()" style="margin-left: 10px;">Save changes</button>
		</div>
		<input type="hidden" id="edit-index">
	    </div>
	</div>

    <!-- Modal per visualizzare il log completo -->
    <div id="log-modal" class="modal">
        <div class="log-modal-content">
            <div class="modal-header">
                <div class="modal-title">Complete log activity</div>
                <span class="close-btn" onclick="closeLogModal()">&times;</span>
            </div>
            <div class="modal-body">
                <div id="full-log-content" class="log-content"></div>
            </div>
            <div style="text-align: right; margin-top: 20px;">
                <button onclick="closeLogModal()">Close</button>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js"></script>
    <script>
        let currentSortColumn = -1;
        let sortDirection = 1;

	function addSwitch() {
	    const hostname = document.getElementById('hostname').value;
	    const ip = document.getElementById('ip').value;
	    const username = document.getElementById('username').value;
	    const password = document.getElementById('password').value;
	    const enablePassword = document.getElementById('enable-password').value;
	    const deviceType = document.getElementById('device-type').value;

	    if (!hostname || !ip || !username || !password) {
		showStatus('Please fill all required fields', 'error');
		return;
	    }

	    const switchData = { 
		hostname, 
		ip, 
		username, 
		password,
		device_type: deviceType
	    };
	    
	    if (enablePassword) {
		switchData.enable_password = enablePassword;
	    }
            
            fetch('/add_switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(switchData),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateSwitchTable();
                    document.getElementById('hostname').value = '';
                    document.getElementById('ip').value = '';
                    document.getElementById('username').value = '';
                    document.getElementById('password').value = '';
                    showStatus('Switch aggiunto con successo', 'success');
                    addToLog(`Device ${hostname} (${ip}) added to the list`);
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            })
            .catch(error => {
                showStatus('Connection error: ' + error, 'error');
            });
        }

        function uploadCSV() {
            const fileInput = document.getElementById('csv-file');
            const file = fileInput.files[0];
            
            if (!file) {
                showStatus('Select a CSV file to load', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('csv_file', file);
            
            fetch('/upload_csv', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showStatus(`Loaded ${data.added} devices from CSV (${data.skipped} already in the list)`, 'success');
                    addToLog(`Loaded ${data.added} devices from CSV file`);
                    updateSwitchTable();
                    fileInput.value = '';
                } else {
                    showStatus('Error: ' + data.message, 'error');
                    addToLog(`CSV load failed: ${data.message}`);
                }
            })
            .catch(error => {
                showStatus('Error: ' + error.message, 'error');
                addToLog(`Error during CSV load: ${error.message}`);
            });
        }

        function sortTable(columnIndex) {
            if (currentSortColumn === columnIndex) {
                sortDirection *= -1;
            } else {
                currentSortColumn = columnIndex;
                sortDirection = 1;
            }
            
            updateSwitchTable();
        }

	function updateSwitchTable() {
	    fetch('/get_switches')
	    .then(response => response.json())
	    .then(switchesData => {
		const tbody = document.getElementById('switches-table-body');
		tbody.innerHTML = '';

		if (switchesData.length === 0) {
		    tbody.innerHTML = '<td colspan="4" style="text-align: center;">No device</td>';
		    return;
		}

		let switchesWithIndex = switchesData.map((sw, index) => ({...sw, originalIndex: index}));

		if (currentSortColumn >= 0) {
		    switchesWithIndex.sort((a, b) => {
		        const keys = ['hostname', 'ip', 'username'];
		        const key = keys[currentSortColumn];
		        const valA = a[key]?.toLowerCase() || '';
		        const valB = b[key]?.toLowerCase() || '';
		        
		        if (valA < valB) return -1 * sortDirection;
		        if (valA > valB) return 1 * sortDirection;
		        return 0;
		    });
		}

		switchesWithIndex.forEach((sw, i) => {
		    const row = document.createElement('tr');
		    row.innerHTML = `
		        <td>${sw.hostname}</td>
		        <td>${sw.ip}</td>
		        <td>${sw.username}</td>
		        <td>
		            <button class="action-btn backup-btn" title="Backup" onclick="backupSwitch(${sw.originalIndex})">
		                <i class="fas fa-download"></i>
		            </button>
		            <button class="action-btn edit-btn" title="Modifica" onclick="openEditModal(${sw.originalIndex})">
		                <i class="fas fa-edit"></i>
		            </button>
		            <button class="action-btn view-btn" title="Visualizza Backup" onclick="viewBackups(${sw.originalIndex})">
		                <i class="fas fa-eye"></i>
		            </button>
		            <button class="action-btn delete-btn" title="Elimina" onclick="deleteSwitch(${sw.originalIndex})">
		                <i class="fas fa-trash"></i>
		            </button>
		        </td>
		    `;
		    tbody.appendChild(row);
		});

		updateSortIcons();
	    })
	    .catch(error => {
		console.error('Device load failed:', error);
		tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: red;">Error during the device update</td></tr>';
	    });
	}

        function updateSortIcons() {
            const headers = document.querySelectorAll('.switch-table th');
            headers.forEach((header, index) => {
                const icon = header.querySelector('i');
                if (icon) {
                    if (index === currentSortColumn) {
                        icon.className = sortDirection === 1 ? 'fas fa-sort-up' : 'fas fa-sort-down';
                    } else {
                        icon.className = 'fas fa-sort';
                    }
                }
            });
        }

	function deleteSwitch(index) {
	    fetch('/get_switches')
	    .then(response => response.json())
	    .then(switchesData => {
		if (index >= 0 && index < switchesData.length) {
		    const hostname = switchesData[index].hostname;
		    
		    if (!confirm(`Are you sure you wanna deleted the device ${hostname}?`)) {
		        return;
		    }

		    fetch('/delete_switch', {
		        method: 'POST',
		        headers: {
		            'Content-Type': 'application/json',
		            'X-CSRFToken': getCSRFToken()
		        },
		        body: JSON.stringify({ index: index }),
		    })
		    .then(response => response.json())
		    .then(data => {
		        if (data.success) {
		            updateSwitchTable();
		            updateSchedulesList();
		            showStatus(`Device ${hostname} deleted successfully`, 'success');
		            addToLog(`Device ${hostname} removed from list`);
		        } else {
		            showStatus('Error: ' + data.message, 'error');
		            addToLog(`ERROR - device delete failed ${hostname}: ${data.message}`);
		        }
		    })
		    .catch(error => {
		        showStatus('Connection error: ' + error, 'error');
		        addToLog(`ERROR - device delete failed: ${error}`);
		    });
		}
	    });
	}

	function backupSwitch(index) {
	    // Prima recuperiamo i dati dello switch per ottenere l'hostname
	    fetch('/get_switches')
	    .then(response => response.json())
	    .then(switchesData => {
		if (index >= 0 && index < switchesData.length) {
		    const switchData = switchesData[index];
		    const statusMessage = `Starting backup for ${switchData.hostname} (${switchData.ip})...`;
		    showStatus(statusMessage, 'success');
		    addToLog(statusMessage);
		    
		    // Poi eseguiamo il backup
		    fetch('/backup_switch', {
		        method: 'POST',
		        headers: {
		            'Content-Type': 'application/json',
		            'X-CSRFToken': getCSRFToken()
		        },
		        body: JSON.stringify({ index: parseInt(index) }),
		    })
		    .then(response => response.json())
		    .then(data => {
		        if (data.success) {
		            const successMessage = `Backup completed for ${data.hostname}`;
		            showStatus(successMessage, 'success');
		            addToLog(successMessage);
		            addToLog(`Config saved at: ${data.filename}`);
		        } else {
		            const errorMessage = `Backup error for ${switchData.hostname}: ${data.message}`;
		            showStatus(errorMessage, 'error');
		            addToLog(`ERROR - backup failed for ${switchData.hostname}: ${data.message}`);
		        }
		    })
		    .catch(error => {
		        const errorMessage = `Connection error for ${switchData.hostname}: ${error}`;
		        showStatus(errorMessage, 'error');
		        addToLog(`ERROR - Connection failed for ${switchData.hostname}: ${error}`);
		    });
		}
	    })
	    .catch(error => {
		const errorMessage = `Error fetching switch data: ${error}`;
		showStatus(errorMessage, 'error');
		addToLog(`ERROR - Failed to get switch data: ${error}`);
	    });
	}

        function backupAllSwitches() {
            addToLog('Starting backup for all devices...');
            
            fetch('/backup_all_switches', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus(`Backup completato per ${data.count} switch`, 'success');
                    data.results.forEach(result => {
                        if (result.success) {
                            addToLog(`Backup completato per ${result.hostname} (${result.ip})`);
                        } else {
                            addToLog(`ERROR during the backup of ${result.hostname}: ${result.message}`);
                        }
                    });
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            })
            .catch(error => {
                showStatus('Connection error: ' + error, 'error');
            });
        }


	function backupAllSwitches() {
	    const statusMessage = 'Starting backup for all devices...';
	    showStatus(statusMessage, 'success');
	    addToLog(statusMessage);
	    
	    fetch('/backup_all_switches', {
		method: 'POST',
		headers: {
		    'Content-Type': 'application/json',
		    'X-CSRFToken': getCSRFToken()
		},
	    })
	    .then(response => response.json())
	    .then(data => {
		if (data.success) {
		    const successMessage = `Backup completed for ${data.count} devices`;
		    showStatus(successMessage, 'success');
		    data.results.forEach(result => {
		        if (result.success) {
		            addToLog(`Backup completed for ${result.hostname} (${result.ip})`);
		        } else {
		            addToLog(`ERROR during the backup of ${result.hostname}: ${result.message}`);
		        }
		    });
		} else {
		    const errorMessage = `Backup error: ${data.message}`;
		    showStatus(errorMessage, 'error');
		}
	    })
	    .catch(error => {
		const errorMessage = `Connection error: ${error}`;
		showStatus(errorMessage, 'error');
	    });
	}
        function viewBackups(index) {
            fetch('/get_switch_backups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ index }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const modal = document.getElementById('backup-modal');
                    const switchName = document.getElementById('modal-switch-name');
                    const backupList = document.getElementById('backup-list');
                    
                    switchName.textContent = data.hostname;
                    backupList.innerHTML = '';
                    
                    if (data.backups.length === 0) {
                        backupList.innerHTML = '<p>No avalaible backup</p>';
                    } else {
                        data.backups.forEach(backup => {
                            const backupItem = document.createElement('div');
                            backupItem.className = 'backup-item';
                            backupItem.textContent = backup.filename;
                            backupItem.onclick = () => loadBackupContent(backup.path);
                            backupList.appendChild(backupItem);
                        });
                    }
                    
                    document.getElementById('backup-content').style.display = 'none';
                    document.getElementById('backup-content-placeholder').style.display = 'block';
                    modal.style.display = 'block';
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            });
        }
        
        function loadBackupContent(filepath) {
            fetch('/get_backup_content', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ filepath }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const contentDiv = document.getElementById('backup-content');
                    const placeholder = document.getElementById('backup-content-placeholder');
                    
                    contentDiv.textContent = data.content;
                    contentDiv.style.display = 'block';
                    placeholder.style.display = 'none';
                    
                    const items = document.querySelectorAll('.backup-item');
                    items.forEach(item => {
                        if (item.textContent.includes(data.filename)) {
                            item.classList.add('active');
                        } else {
                            item.classList.remove('active');
                        }
                    });
                }
            });
        }

        function closeModal() {
            document.getElementById('backup-modal').style.display = 'none';
        }

	function openEditModal(index) {
	    fetch('/get_switches')
	    .then(response => response.json())
	    .then(switchesData => {
		if (index >= 0 && index < switchesData.length) {
		    const switchData = switchesData[index];
		    
		    document.getElementById('edit-hostname').value = switchData.hostname;
		    document.getElementById('edit-ip').value = switchData.ip;
		    document.getElementById('edit-username').value = switchData.username;
		    document.getElementById('edit-password').value = '';
		    document.getElementById('edit-enable-password').value = '';
		    document.getElementById('edit-index').value = index;
		    
		    document.getElementById('edit-modal').style.display = 'block';
		}
	    });
	}

	function saveEditedSwitch() {
	    const index = document.getElementById('edit-index').value;
	    const hostname = document.getElementById('edit-hostname').value;
	    const ip = document.getElementById('edit-ip').value;
	    const username = document.getElementById('edit-username').value;
	    const password = document.getElementById('edit-password').value;
	    const enablePassword = document.getElementById('edit-enable-password').value;

	    if (!hostname || !ip || !username) {
		showStatus('Please fill all required fields', 'error');
		return;
	    }

	    const switchData = { 
		index: parseInt(index),
		hostname: hostname,
		ip: ip,
		username: username
	    };
	    
	    if (password) {
		switchData.password = password;
	    }
	    
	    if (enablePassword) {
		switchData.enable_password = enablePassword;
	    }
	    
	    fetch('/update_switch', {
		method: 'POST',
		headers: {
		    'Content-Type': 'application/json',
		    'X-CSRFToken': getCSRFToken()
		},
		body: JSON.stringify(switchData),
	    })
	    .then(response => response.json())
	    .then(data => {
		if (data.success) {
		    updateSwitchTable();
		    updateSchedulesList();
		    closeEditModal();
		    showStatus('Device data updated successfully', 'success');
		    addToLog(`Device ${hostname} (${ip}) data updated`);
		} else {
		    showStatus('Error: ' + data.message, 'error');
		}
	    });
	}

	function closeEditModal() {
	    document.getElementById('edit-modal').style.display = 'none';
	}

	function showStatus(message, type) {
	    const statusElement = document.getElementById('status-message');
	    statusElement.textContent = message;
	    statusElement.className = 'status ' + type;
	    statusElement.style.display = 'block';
	    
	    // Auto-hide after 5 seconds
	    setTimeout(() => {
		statusElement.style.display = 'none';
	    }, 5000);
	}

	function addToLog(message) {
	    const logElement = document.getElementById('log');
	    const timestamp = new Date().toLocaleTimeString();
	    const messageDiv = document.createElement('div');
	    messageDiv.textContent = `[${timestamp}] ${message}`;
	    
	    // Aggiunge classi in base al tipo di messaggio
	    if (message.includes('ERROR:')) {
		messageDiv.style.color = '#ff6b6b';
	    } else if (message.includes('Starting') || message.includes('Connected') || message.includes('Executing')) {
		messageDiv.style.color = '#51cf66';
	    } else if (message.includes('completed')) {
		messageDiv.style.color = '#339af0';
	    }
	    
	    logElement.insertBefore(messageDiv, logElement.firstChild);
	    logElement.scrollTop = 0;
	}

        function viewFullLog() {
            fetch('/get_full_log')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const modal = document.getElementById('log-modal');
                    const logContent = document.getElementById('full-log-content');
                    
                    logContent.textContent = data.log;
                    modal.style.display = 'block';
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            });
        }

        function closeLogModal() {
            document.getElementById('log-modal').style.display = 'none';
        }

	window.onclick = function(event) {
	    const backupModal = document.getElementById('backup-modal');
	    const editModal = document.getElementById('edit-modal');
	    const logModal = document.getElementById('log-modal');
	    
	    if (event.target === backupModal) {
		backupModal.style.display = 'none';
	    }
	    if (event.target === editModal) {
		editModal.style.display = 'none';
	    }
	    if (event.target === logModal) {
		logModal.style.display = 'none';
	    }
	}

        function showScheduleOptions() {
            const type = document.getElementById('schedule-type').value;
            document.querySelectorAll('.schedule-option').forEach(option => {
                option.classList.remove('active');
            });
            
            if (type === 'once') {
                document.getElementById('once-option').classList.add('active');
            } else if (type === 'weekly') {
                document.getElementById('weekly-option').classList.add('active');
            } else if (type === 'monthly') {
                document.getElementById('monthly-option').classList.add('active');
            } else if (type === 'yearly') {
                document.getElementById('yearly-option').classList.add('active');
            }
        }

        function addSchedule() {
            const type = document.getElementById('schedule-type').value;
            const time = document.getElementById('schedule-time').value;
            
            const scheduleData = {
                type: type,
                time: time,
                enabled: true
            };
            
            if (type === 'once') {
                const date = document.getElementById('schedule-date').value;
                if (!date) {
                    showStatus('Seleziona una data valida', 'error');
                    return;
                }
                scheduleData.date = date;
            } else if (type === 'weekly') {
                scheduleData.day_of_week = document.getElementById('schedule-day-week').value;
            } else if (type === 'monthly') {
                scheduleData.day = document.getElementById('schedule-day-month').value;
            } else if (type === 'yearly') {
                scheduleData.month = document.getElementById('schedule-month').value;
                scheduleData.day = document.getElementById('schedule-day-year').value;
            }
            
            fetch('/add_schedule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(scheduleData),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus('Pianificazione aggiunta con successo', 'success');
                    updateSchedulesList();
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            });
        }

        function updateSchedulesList() {
            fetch('/get_schedules')
            .then(response => response.json())
            .then(schedules => {
                const list = document.getElementById('schedules-list');
                list.innerHTML = '';
                
                if (schedules.length === 0) {
                    list.innerHTML = '<p>No active schedule</p>';
                    return;
                }
                
                schedules.forEach(schedule => {
                    const item = document.createElement('div');
                    item.className = 'schedule-item';
                    
                    const description = getScheduleDescription(schedule);
                    
                    item.innerHTML = `
                        <div class="schedule-item-header">
                            <span>${description}</span>
                            <div class="schedule-item-actions">
                                <button class="action-btn ${schedule.enabled ? 'edit-btn' : 'backup-btn'}" 
                                    onclick="toggleSchedule('${schedule.id}', ${!schedule.enabled})">
                                    <i class="fas fa-${schedule.enabled ? 'pause' : 'play'}"></i>
                                </button>
                                <button class="action-btn delete-btn" onclick="deleteSchedule('${schedule.id}')">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div>Backup globale di tutti gli switch</div>
                        <div>Prossima esecuzione: ${schedule.next_run || 'N/A'}</div>
                    `;
                    
                    list.appendChild(item);
                });
            });
        }

        function toggleSchedule(scheduleId, enable) {
            fetch('/toggle_schedule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ id: scheduleId, enabled: enable }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus(`Pianificazione ${enable ? 'attivata' : 'disattivata'}`, 'success');
                    updateSchedulesList();
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            });
        }

        function deleteSchedule(scheduleId) {
            if (!confirm('Sei sicuro di voler eliminare questa pianificazione?')) {
                return;
            }
            
            fetch('/delete_schedule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ id: scheduleId }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus('Pianificazione eliminata', 'success');
                    updateSchedulesList();
                } else {
                    showStatus('Error: ' + data.message, 'error');
                }
            });
        }

        function getScheduleDescription(schedule) {
            let desc = '';
            const time = schedule.time || '00:00';
            
            switch (schedule.type) {
                case 'once':
                    desc = `Una volta il ${schedule.date} alle ${time}`;
                    break;
                case 'daily':
                    desc = `Giornaliero alle ${time}`;
                    break;
                case 'weekly':
                    const days = ['Domenica', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato'];
                    desc = `Settimanale ogni ${days[parseInt(schedule.day_of_week)]} alle ${time}`;
                    break;
                case 'monthly':
                    desc = `Mensile il giorno ${schedule.day} alle ${time}`;
                    break;
                case 'yearly':
                    const months = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                                  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'];
                    desc = `Annuale il ${schedule.day} ${months[parseInt(schedule.month) - 1]} alle ${time}`;
                    break;
            }
            
            return desc;
        }
	function getCSRFToken() {
	    const name = 'csrf_token';
	    const cookies = document.cookie.split(';');
	    for (let cookie of cookies) {
		let [key, value] = cookie.trim().split('=');
		if (key === name) return decodeURIComponent(value);
	    }
	    return '';
	}

        function exportSwitchesToCSV() {
            fetch('/export_switches_csv')
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'switches_backup_' + new Date().toISOString().slice(0, 10) + '.csv';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                showStatus('Esportazione CSV completata', 'success');
                addToLog('Esportata lista switch in formato CSV');
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            const tbody = document.getElementById('switches-table-body');
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Caricamento switch in corso...</td></tr>';
            
            updateSwitchTable();
            showScheduleOptions();
            updateSchedulesList();
            
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('schedule-date').min = today;
            document.getElementById('schedule-date').value = today;
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=False)
	version = "1.0.1"
