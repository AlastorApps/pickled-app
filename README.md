![PICKLED logo](https://raw.githubusercontent.com/AlastorApps/pickled/refs/heads/main/static/PICKLED_logo320.png)



# PICKLED
### Platform for Instant Config Keep & Lightweight Export Daemon
**Network Configuration Backup Manager**  
Developed by **Luca Armiraglio** & **Mattia Mattavelli**

---

>_"Because broken routers don’t explain themselves."_
>— Anonymous Network Engineer

---

## Overview
**PICKLED** is a **lightweight and ultra-efficient web application** designed for network administrators to automate and manage **network device configuration backups** (switches, routers, etc.) over SSH.

Forget heavy platforms and costly infrastructure: **PICKLED runs flawlessly even on a Raspberry Pi Zero**, requiring **minimal system resources** while delivering enterprise-grade features such as **secure credential management**, **flexible scheduling**, and **configuration versioning**.

---

## Key Features
### Device Management
- **Centralized Device Inventory** with connection details.
- **Secure Credential Storage** using AES-256 encryption.
- **Bulk Import/Export via CSV**.
- Easy device addition, editing, and removal.

### Configuration Backup
- **Instant Backups** with a single click.
- **Advanced Scheduling**: Daily, weekly, monthly, custom intervals.
- **Global Backup Execution** for all devices.
- **Version Control** with historical config snapshots.

### Backup Management
- **Visual Config Viewer & Diff Comparison**.
- **Secure Storage with Access Controls**.
- **Quick Export of Config Files** for offline use.

### Scheduling System
- **Flexible Backup Schedules** with per-device customization.
- **Enable/Disable Schedules Dynamically**.
- **Global Scheduling for All Devices**.
- **Visual Feedback on Upcoming Tasks**.

### Security & Access Control
- **Role-Based Access** with secure login.
- **CSRF Protection** on all forms.
- **AES-256 Encryption** for sensitive data in transit and at rest.
- **Detailed Activity Logging** for full traceability.

### Monitoring & Reporting
- **Live Logs & Historical Archives**.
- **Immediate Backup Feedback**.
- **Comprehensive Error Reporting**.

---

## Technical Specifications
- **Backend**: Python (Flask)
- **Frontend**: HTML5, CSS3, JavaScript
- **SSH Connectivity**: Netmiko
- **Task Scheduling**: APScheduler
- **Encryption**: Python Cryptography (Fernet AES-256)

### System Requirements:
- Python 3.6+
- Required Packages:
  ```bash
  flask flask-wtf netmiko apscheduler cryptography
  ```

---

## Why PICKLED?
- **Ultra-Lightweight Deployment**: Runs perfectly on **Raspberry Pi Zero** or similar low-power devices.
- **No Heavy Databases** or complex dependencies.
- **Single-File Daemon**: Fast, portable, and easy to maintain.
- **Zero Infrastructure Investment**: Deploy in minutes without expensive hardware.
- **Blazing Fast & Minimal Footprint** for hundreds of devices.

---

## Installation & Quick Start
### Recommended Method:
```bash
wget https://github.com/AlastorApps/pickled-app/raw/main/install.sh
chmod +x install.sh
./install.sh
```

### Manual Installation:
```bash
git clone https://github.com/AlastorApps/pickled-app.git
cd pickled
pip install -r requirements.txt
python pickled.py
```

### Access the Web Interface:
- URL: [http://localhost:5000](http://localhost:5000)
- Default Credentials:  
  **Username**: `jar`  
  **Password**: `cucumber`

---

## Production Deployment Recommendations
- Run as a **systemd service**.
- Enable **SSL/TLS Encryption**.
- Change default credentials.
- Secure file system permissions for backups.

---

## Usage Examples
### Add a New Device
1. Go to **"Add Device"**.
2. Fill in hostname, IP, and credentials.
3. Save.

### Create a Backup Schedule
1. Navigate to **"Backup Scheduler"**.
2. Select schedule type (daily, weekly, etc.).
3. Define frequency and save.

### Perform a Manual Backup
1. Locate device in the list.
2. Click the **Backup** icon.
3. Check results in the **Activity Log**.

---

## Logs & Troubleshooting
- Logs stored in `/logs/`
- Log rotation: Daily, kept for 12 days.
- Common Issues:
  - **SSH Connection Failures**: Check device reachability & credentials.
  - **Permission Errors**: Ensure correct directory access rights.
  - **Scheduling Problems**: Verify system time & timezone.

---

## Roadmap
- **Config Comparison Tool** with visual diffs.
- **Alert System** for failed backups.
- **REST API** for external integrations.
- **Multi-User Support** with role-based permissions.
- **Advanced Export Automation**.

---

## License
GPLv3 — Free Software Forever.

---

### Built for speed. Runs anywhere.

---

### TL;DR:
> **PICKLED** is a **fast, no-nonsense backup daemon for network devices**, runs even on a **Raspberry Pi Zero**, with **zero infrastructure costs**, and **all the essentials packed into a single file**.
