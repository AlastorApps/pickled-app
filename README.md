![PICKLED logo](https://github.com/AlastorApps/pickled/blob/main/PICKLED_logo320.png)


# PICKLED - Platform for Instant Config Keep & Lightweight Export Daemon
## Network Configuration Backup Manager developed by Luca Armiraglio & Mattia Mattavelli

__Because broken routers don’t explain themselves__

## Overview

Pickled is a comprehensive web application designed for network administrators to manage and automate backups of network device configurations (e.g., switches, routers) via SSH. It offers a secure, centralized platform for configuration management with advanced scheduling and version control features.


## Key Features
### 1. Device Management

 Centralized Inventory: Maintain a complete inventory of network devices, including all connection details.
 Secure Credential Storage: All credentials are encrypted using AES-256 encryption before being stored.
 Bulk Operations: Add multiple devices simultaneously via CSV import/export.
 Device Configuration: Easily update or remove devices from the system.

### 2. Configuration Backup

On-Demand Backups: Initiate immediate backups of device configurations.

 Scheduled Backups: Automate backups with flexible scheduling options:
 Daily, weekly, monthly, or yearly intervals
 Custom time settings for each schedule
 Global Backup: Execute backups for all devices with a single command.
 Configuration Versioning: Maintain historical versions of device configurations.


### 3. Backup Management

 Configuration Viewer: View and compare different versions of device configurations.
 Secure Storage: Backups are securely stored with proper access controls.
 Quick Access: Easily locate and retrieve specific configuration versions.
 Export Capabilities: Download configuration files for offline analysis or archiving.


### 4. Scheduling System

 Flexible Scheduling: Create multiple backup schedules with different frequencies.
 Schedule Management: Enable or disable schedules without deleting them.
 Visual Feedback: View upcoming scheduled operations through the web interface.
 Global Scheduling: Apply schedules to all devices at once.


### 5. Security Features

 Role-Based Access: Secure web interface with login protection.
 CSRF Protection: All forms are protected against Cross-Site Request Forgery.
 Encrypted Storage: Sensitive data is encrypted both in transit and at rest.
 Activity Logging: All operations are comprehensively logged.


### 6. Monitoring and Reporting

 Real-Time Logs: View system activities as they happen.
 Historical Logs: Access archived logs for troubleshooting.
 Backup Status: Receive immediate feedback on backup operations.
 Error Reporting: Detailed error messages for failed operations.


## Technical Specifications
### Core Technologies

 Backend: Python (Flask framework)
 Frontend: HTML5, CSS3, JavaScript
 SSH Connectivity: Netmiko library
 Scheduling: APScheduler
 Encryption: cryptography (Fernet)


### System Requirements

 Python: __Version 3.6+__
 Required Python Packages:

```
flask flask-wtf netmiko apscheduler cryptography
```


### Security Implementation

 AES-256 encryption for stored credentials
 CSRF protection on all forms
 Secure session management
 Configuration files stored with proper file permissions
 Dedicated system user for service operation

##  and Setup
### Quick Start

 Install dependencies:
```
pip install flask flask-wtf netmiko apscheduler cryptography
```
Run the application:
```
python3 pickled.py
```
or just execute our __install.sh__ script.

 Access the web interface:
 http://localhost:5000
 Default credentials:
 Username: jar
 Password: cucumber

### Production Deployment Recommendations

 Set up as a systemd service
 Enable SSL/TLS encryption
 Change default credentials
 Set appropriate file permissions

## Usage Examples
### Adding a New Device

 Navigate to the "Add Device" section
 Enter device details (hostname, IP address, credentials)
 Save to add the device to the inventory

### Creating a Backup Schedule

 Go to the "Backup Scheduler" section
 Select schedule type (daily, weekly, etc.)
 Configure time and frequency settings
 Save the schedule

### Performing a Manual Backup

 Locate the device in the device list
 Click the backup icon
 View the result in the activity log

## Maintenance and Troubleshooting
### Log Files

 Logs are stored in the logs/ directory
 Logs are rotated daily and retained for 12 days

### Common Issues

 Connection Failures: Verify device accessibility and credentials
 Permission Errors: Ensure correct directory permissions for backups
 Scheduling Issues: Check system time and timezone settings

### Roadmap (Planned Features)

 Configuration comparison tool
 Alerting system for failed backups
 REST API for integration with external tools
 Multi-user support with role-based access control


Fast and lighweight single-file web application for Cisco network devices configuration backup - works with ssh
