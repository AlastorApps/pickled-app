#!/bin/bash

# Pickled Network Configuration Backup Manager - Installation Script

# Configuration variables
APP_NAME="pickled"
INSTALL_DIR="/opt/${APP_NAME}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
GITHUB_REPO="https://github.com/AlastorApps/pickled.git" 
GITHUB_RAW="https://raw.githubusercontent.com/AlastorApps/pickled/refs/heads/main/pickled.py"  

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


function show_pickle_art() {
cat << "EOF"

                                                                                
                              .+%#**%*-                                         
                            +#---------**                                       
                          =#-------------%                                      
                         #+--------------*-                                     
                        #----------------=+                                     
                       %-----------------*=                                     
                      *+-----=====-----++%+-                                    
                   -%###%%%%%-----=%-**-----**                                  
                     %-----+*--*%=-%+#--%%--*:                                  
                    =*-----+#--#%+=#-*==%%--%                 .-=               
                    %-------=#***#*---*#**#*      .-+**#%%%#*++**%.             
                   -#------------------#:      %*+*****##########%              
                   *+------------+%%#--%      #**###############%+              
                   #=-----------------++      %+########=*######%               
                   %------------------#%=    =#*####=-#+=++####%+               
                  .#-------=----------%-=%:  %=###*-+#=-#+-+###%.               
                  .#--------%=--------%----*%#*######+=#######%%                
                  .#----=-----+###*==+#%%---#*########%#######%:                
                   #-----%*----------*-#%%%%%+#####%*%  #%#####                 
                   %=------+#%%%%%%%#%%%*#%%*#####%      .-%#%-                 
                   **=-----=%#*+=*%#*+*#*#%%*####%:.=     =%%:                  
                   .%==-----%%%#####**+===##*####%:       +-                    
                    -#==-------=+*#%%%###%%%%%#=. .+#:     *=                   
                     :#==---------=#:  .:.           *=     +*                  
                      .*#+==----+%#.                  #:                        
                    :--===*####*====--:               :*                        
                                                                                
                                                                                
        -%%%%%%%% .%%  %%%%%%%%  %%*   #%# -%%      -%%%%%%%+ %%%%%%%%+         
        -%%   .%%..%% .%%:   #%* %%*  %%*  -%%      #%#       %%=   +%%.        
        -%%    %%:.%% .%%.   :   %%* #%*   -%%      #%*       %%=    %%.        
        -%%#**#%%..%% .%%.       %%%%%%    -%%      #%%%%%%*  %%=    %%.        
        -%%%%%%%. .%% .%%.   =.  %%* +%%   -%%      #%*       %%=    %%.        
        -%%       .%% .%%-   #%* %%*  *%#  -%%.     #%#       %%+   =%%         
        -%%        %%  #%%%%%%%  %%*   +%%  #%%%%%% :%%%%%%%+ #%%%%%%%=             
                                                                                                           
  Platform for Instant Config Keep & Lightweight Export Daemon

EOF
}


function show_menu {
    clear
    echo -e "${GREEN}╔══════════════════════════════════════════════╗"
    echo -e "║       Pickled Installation Menu              ║"
    echo -e "╠══════════════════════════════════════════════╣"
    echo -e "║ 1. Standard Installation (wget)              ║"
    echo -e "║ 2. Git Clone Installation                    ║"
    echo -e "║ 3. Exit                                      ║"
    echo -e "╚══════════════════════════════════════════════╝${NC}"
    echo -n "Please choose an option [1-3]: "
}

function install_dependencies {
    echo -e "\n${YELLOW}[1/5] Installing system dependencies...${NC}"
    apt-get update >/dev/null 2>&1
    apt-get install -y python3 python3-pip git >/dev/null 2>&1
    
    echo -e "\n${YELLOW}[2/5] Installing Python packages...${NC}"
    pip install flask flask-wtf paramiko apscheduler cryptography >/dev/null 2>&1
}

function setup_application {
    echo -e "\n${YELLOW}[3/5] Setting up application directory...${NC}"
    mkdir -p ${INSTALL_DIR}
    cd ${INSTALL_DIR}
    
    if [ $1 == "wget" ]; then
        echo "Downloading application from GitHub..."
        wget -q ${GITHUB_RAW} -O pickled.py
    else
        echo "Cloning repository from GitHub..."
        git clone ${GITHUB_REPO} .
    fi
    
    # Create necessary directories
    mkdir -p logs backups
}

function configure_permissions {
    echo -e "\n${YELLOW}[4/5] Configuring system user...${NC}"
    if ! id "${APP_NAME}-user" &>/dev/null; then
        useradd --system --no-create-home --shell /usr/sbin/nologin ${APP_NAME}-user
    fi

    # Set permissions
    chown -R ${APP_NAME}-user:${APP_NAME}-user ${INSTALL_DIR}
    chmod 750 ${INSTALL_DIR}
    chmod 740 ${INSTALL_DIR}/pickled.py
    chown -R ${APP_NAME}-user:${APP_NAME}-user ${INSTALL_DIR}/logs ${INSTALL_DIR}/backups
}

function setup_service {
    echo -e "\n${YELLOW}[5/5] Configuring system service...${NC}"
    cat > ${SERVICE_FILE} <<EOL
[Unit]
Description=Pickled - Network Configuration Backup Manager
After=network.target
StartLimitIntervalSec=60

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/pickled.py
WorkingDirectory=${INSTALL_DIR}
User=${APP_NAME}-user
Group=${APP_NAME}-user
Restart=on-failure
RestartSec=5s
Environment=PYTHONUNBUFFERED=1

# Security hardening
ProtectSystem=full
ProtectHome=true
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=true
RestrictRealtime=true
SystemCallArchitectures=native
CapabilityBoundingSet=
LockPersonality=true
MemoryDenyWriteExecute=true
RemoveIPC=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd
    systemctl daemon-reload
    systemctl enable ${APP_NAME}.service
    systemctl start ${APP_NAME}.service
}

function complete_installation {
    # Verify installation
    echo -e "\n${GREEN}╔══════════════════════════════════════════════╗"
    echo -e "║          Installation Complete               ║"
    echo -e "╠══════════════════════════════════════════════╣"
    echo -e "║ Pickled has been successfully installed!     ║"
    echo -e "║                                              ║"
    echo -e "║ Access the web interface at:                 ║"
    echo -e "║ http://$(hostname -I | awk '{print $1}'):5000       ║"
    echo -e "║                                              ║"
    echo -e "║ Default credentials:                         ║"
    echo -e "║ - Username: jar                              ║"
    echo -e "║ - Password: cucumber                         ║"
    echo -e "║                                              ║"
    echo -e "║ Management commands:                         ║"
    echo -e "║ sudo systemctl status pickled.service        ║"
    echo -e "║ sudo systemctl restart pickled.service       ║"
    echo -e "║ journalctl -u pickled.service -f             ║"
    echo -e "╚══════════════════════════════════════════════╝${NC}"
}

function standard_installation {
    echo -e "\n${GREEN}Starting standard installation...${NC}"
    install_dependencies
    setup_application "wget"
    configure_permissions
    setup_service
    complete_installation
}

function git_installation {
    echo -e "\n${GREEN}Starting Git-based installation...${NC}"
    install_dependencies
    setup_application "git"
    configure_permissions
    setup_service
    complete_installation
}

show_pickle_art

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}This script must be run as root. Use sudo.${NC}" >&2
    exit 1
fi

while true; do
    show_menu
    read choice
    case $choice in
        1)
            standard_installation
            break
            ;;
        2)
            git_installation
            break
            ;;
        3)
            echo -e "\n${YELLOW}Installation canceled.${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}Invalid option. Please choose 1, 2, or 3.${NC}"
            sleep 2
            ;;
    esac
done

exit 0
