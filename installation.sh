#!/bin/bash

#################################
# PICKLED - Installation Script #
#################################

# Configuration variables
APP_NAME="pickled"
INSTALL_DIR="/opt/${APP_NAME}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
GITHUB_REPO="https://github.com/AlastorApps/pickled.git"
GITHUB_RAW="https://raw.githubusercontent.com/AlastorApps/pickled/refs/heads/main/pickled.py"

# Colors for ASCII Art
LIGHTGREEN=$'\033[38;5;120m'
PETROLGREEN=$'\033[38;5;30m'
NCASCII=$'\033[0m'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color


###########################
# Running shell detection #
###########################

[ -n "$BASH_VERSION" ] || {
    shell_used=$(ps -p $$ -o comm=)
    printf "${RED}ERROR:${NC} This script requires bash. Detected: ${YELLOW}%s${NC}\n" "$shell_used"
    exit 1
}

# Strict bash mode and pipefail protection
set -euo pipefail


####################################################################
# System integrity checks - check if needed commands are available #
####################################################################
missing=()
for cmd in apt-get systemctl find git wget python3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -ne 0 ]; then
    echo -e "${RED}Missing${NC} required commands: ${YELLOW}${missing[*]}${NC}"
    exit 1
fi


###########################
# Checking if run as sudo #
###########################
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}This script must be run as root. Use sudo.${NC}" >&2
    exit 1
fi

#######################################
# Setting up logging for setup script #
#######################################
LOGFILE="./pickled_install.log"

if [ -f "$LOGFILE" ]; then
    rm "$LOGFILE"
fi

touch "$LOGFILE"
chmod 644 "$LOGFILE"
exec > >(tee -a "$LOGFILE") 2>&1


#########################
# FUNCTION DECLARATIONS #
#########################

function show_pickle_art() {
clear
cat << EOF
${LIGHTGREEN}
                                                                                
                              .+%#**%*-                                         
                            +#---------**                                       
                          =#-------------%                                      
                         #+--------------*-                                     
                        #----------------=+                                     
                       %-----------------*=                                     
                      *+-----=====-----++%+-                                    
                   -%###%%%%%-----=%-**-----**                                  
                     %-----+*--${PETROLGREEN}*%${LIGHTGREEN}=-%+#--${PETROLGREEN}%%${LIGHTGREEN}--*:                                  
                    =*-----+#--${PETROLGREEN}#%${LIGHTGREEN}+=#-*==${PETROLGREEN}%%${LIGHTGREEN}--%                 .-=               
                    %-------=#***#*---*#**#*      ${PETROLGREEN}.-+**#%%%#*++**%.             ${LIGHTGREEN}
                   -#------------------#:      ${PETROLGREEN}%*+*****##########%              ${LIGHTGREEN}
                   *+------------${PETROLGREEN}+%%#${LIGHTGREEN}--%      ${PETROLGREEN}#**###############%+              ${LIGHTGREEN}
                   #=-----------------++      ${PETROLGREEN}%+########=*######%               ${LIGHTGREEN}
                   %------------------#%=    ${PETROLGREEN}=#*####=-#+=++####%+               ${LIGHTGREEN}
                  .#-------=----------%-=%:  ${PETROLGREEN}%=###*-+#=-#+-+###%.               ${LIGHTGREEN}
                  .#--------%=--------%----*%${PETROLGREEN}#*######+=#######%%                ${LIGHTGREEN}
                  .#----=-----+###*==+#%%---${PETROLGREEN}#*########%#######%:                ${LIGHTGREEN}
                   #-----%*----------*-${PETROLGREEN}#%%%%%+#####%*%  #%#####                 ${LIGHTGREEN}
                   %=------+${PETROLGREEN}#%%%%%%%#%%%*#%%*#####%      .-%#%-                 ${LIGHTGREEN}
                   **=-----=${PETROLGREEN}%#*+=*%#*+*#*#%%*####%:.=     =%%:                  ${LIGHTGREEN}
                   .%==-----${PETROLGREEN}%%%#####**+===##*####%:       +-                    ${LIGHTGREEN}
                    -#==-------=+*${PETROLGREEN}#%%%###%%%%%#=. .+#:     *=                   ${LIGHTGREEN}
                     :#==---------=#:  .:.           *=     +*                  
                      .*#+==----+%#.                  #:                        
                    :--===*####*====--:               :*                        
                                                                                
                                                                                ${PETROLGREEN}
        -%%%%%%%% .%%  %%%%%%%%  %%*   #%# -%%      -%%%%%%%+ %%%%%%%%+         
        -%%   .%%..%% .%%:   #%* %%*  %%*  -%%      #%#       %%=   +%%.        
        -%%    %%:.%% .%%.   :   %%* #%*   -%%      #%*       %%=    %%.        
        -%%#**#%%..%% .%%.       %%%%%%    -%%      #%%%%%%*  %%=    %%.        
        -%%%%%%%. .%% .%%.   =.  %%* +%%   -%%      #%*       %%=    %%.        
        -%%       .%% .%%-   #%* %%*  *%#  -%%.     #%#       %%+   =%%         
        -%%        %%  #%%%%%%%  %%*   +%%  #%%%%%% :%%%%%%%+ #%%%%%%%=             
                                                                                                           
         Platform for Instant Config Keep & Lightweight Export Daemon
             - Because broken routers can't explain themselves -
${NCASCII}
EOF
}

function show_menu {
        local width=60
        local title="PICKLED Installation Menu"
        local lines=(
			"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
			"Logging setup to: ${LOGFILE}"
			"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
			"1. Standard Installation (wget)"
			"2. Git Clone Installation"
			"3. Update Existing Installation - standard (wget)"
			"4. Update Existing Installation - Git clone"
			"5. Dry-run / Check only"
			"6. Exit"
        )

        center_text() {
                local text="$1"
                local width="$2"
                local padding=$(( (width - ${#text}) / 2 ))
                printf "%*s%s%*s\n" "$padding" "" "$text" $((width - padding - ${#text} + 2)) "║"
        }

        echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════╗"

        printf "║ "
        center_text "$title" "$((width - 2))"

        for line in "${lines[@]}"; do
                printf "║ %-*s ║\n" $((width - 4)) "$line"
        done

        echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
	echo -n "Please choose an option [1-6]: "
}

function dry_run_check {
    echo -e "\n${CYAN}Performing system check (dry run)...${NC}"
    echo -e "${YELLOW}- Current user: ${NC}${YELLOW}$(id -un) (UID: $(id -u))${NC}"
    echo -e "${YELLOW}- Required commands:${NC}"

    local missing=()
    for cmd in apt-get systemctl git wget python3; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
            echo -e "  ${RED}✗ $cmd${NC}"
        else
            echo -e "  ${GREEN}✓ $cmd${NC}"
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "\n${RED}System is missing required commands.${NC}"
        exit 1
    else
        echo -e "\n${GREEN}All required commands are available.${NC}"
        exit 0
    fi
}

function install_dependencies {
	echo -e "\n${YELLOW}[1/5] Installing system dependencies...${NC}"
	apt-get update >/dev/null 2>&1

	if [ "$1" == "git" ]; then
		apt-get install -y python3 python3-pip git >/dev/null 2>&1
	elif [ "$1" == "nogit" ]; then
		apt-get install -y python3 python3-pip >/dev/null 2>&1
	fi

	echo -e "\n${YELLOW}[2/5] Installing Python packages...${NC}"
	#pip install flask flask-wtf netmiko apscheduler cryptography >/dev/null 2>&1
	apt-get install -y python3-flask python3-flaskext.wtf python3-netmiko python3-apscheduler python3-cryptography git >/dev/null 2>&1
}

function setup_application {
    echo -e "\n${YELLOW}[3/5] Setting up application directory...${NC}"
    mkdir -p ${INSTALL_DIR}
    cd ${INSTALL_DIR}

    if [ "$1" == "wget" ]; then
        echo "Downloading application from GitHub..."
        wget -q ${GITHUB_RAW} -O pickled.py
    else
        echo "Cloning repository from GitHub..."
        git clone ${GITHUB_REPO} .
    fi

    # Create app directories
    mkdir -p logs backups
}

function update_application {
	echo -e "\n${YELLOW}[3/5] Updating application files and directories...${NC}"
	cd "${INSTALL_DIR}"
	
	git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null || true

	if [ "$1" == "wget" ]; then
		echo "Downloading update with wget from GitHub..."
		wget -q ${GITHUB_RAW} -O pickled.py
	elif [ "$1" == "git" ]; then
		echo "Updating via Git repository..."
		if [ -d ".git" ]; then
			git pull --rebase --autostash
		else
			echo "No existing Git repository found, cloning fresh copy..."
			find . -mindepth 1 \
				-not -path './logs*' \
				-not -path './backups*' \
				-not -path './encryption.key' \
				-not -path './.git*' \
				-exec rm -rf {} +
			git clone ${GITHUB_REPO} .
		fi
	fi

	# Ensure directories exist
	mkdir -p logs backups
}

function set_permissions {
	if [ "$1" == "install" ]; then
		echo -e "\n${YELLOW}[4/5] Configuring system user and permissions...${NC}"
	elif [ "$1" == "update" ]; then
		echo -e "\n${YELLOW}[4/5] Updating system permissions...${NC}"
	fi
	
	# Set application user
	if ! id "${APP_NAME}-user" &>/dev/null; then
		useradd --system --no-create-home --shell /usr/sbin/nologin ${APP_NAME}-user
	fi
	
	# Set appfiles permissions
	[ -d "${INSTALL_DIR}" ] && chown -R ${APP_NAME}-user:${APP_NAME}-user "${INSTALL_DIR}" && chmod 750 "${INSTALL_DIR}"
	[ -f "${INSTALL_DIR}/pickled.py" ] && chmod 740 "${INSTALL_DIR}/pickled.py"
	
	# If updating, set existing folder permissions
	if [ "$1" == "update" ]; then
		for sub in logs backups; do
			[ -d "${INSTALL_DIR}/${sub}" ] && chown -R ${APP_NAME}-user:${APP_NAME}-user "${INSTALL_DIR}/${sub}"
		done
	fi
}

function setup_service {
	echo -e "\n${YELLOW}[5/5] Configuring system service...${NC}"
	
    cat > ${SERVICE_FILE} <<EOL
[Unit]
Description=PICKLED - Platform for Instant Config Keep & Lightweight Export Daemon
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
	local width=60
	local title="Installation Complete"
	
	local ip_address=$(hostname -I | awk '{print $1}')
	# fallback value, if hostname returns nothing
	ip_address=${ip_address:-localhost}
	
	local lines=(
		"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
		"PICKLED has been successfully installed!"
		""
		"Access the web interface at:"
		http://${ip_address}:5000
		""
		"Default Credentials:"
		" - Username: jar"
		" - Password: cucumber"
		""
		"Management Commands:"
		"sudo systemctl status pickled.service"
		"sudo systemctl restart pickled.service"
		"sudo journalctl -u pickled.service -f"
	)

	center_text() {
		local text="$1"
		local width="$2"
		local padding=$(( (width - ${#text}) / 2 ))
		printf "%*s%s%*s\n" "$padding" "" "$text" $((width - padding - ${#text} + 2)) "║"
	}

	echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════╗"

	printf "║ "
	center_text "$title" "$((width - 2))"

	#	for line in "${lines[@]}"; do
	#		printf "║ %-*s ║\n" $((width - 4)) "$line"
	#	done

	for line in "${lines[@]}"; do
		if [[ "$line" == http* ]]; then
			printf "║ ${CYAN}%-*s${GREEN} ║\n" $((width - 4)) "$line"
		else
			printf "║ %-*s ║\n" $((width - 4)) "$line"
		fi
	done

	echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
}

function standard_installation {
    echo -e "\n${GREEN}Starting standard installation...${NC}"
    install_dependencies "nogit"
    setup_application "wget"
    set_permissions "install"
    setup_service
    complete_installation
}

function git_installation {
    echo -e "\n${GREEN}Starting Git-based installation...${NC}"
    install_dependencies "git"
    setup_application "git"
    set_permissions "install"
    setup_service
    complete_installation
}

function standard_update {
	echo -e "\n${GREEN}Starting standard (wget) update...${NC}"
	systemctl stop ${APP_NAME}.service
	install_dependencies "nogit"
	update_application "wget"
	set_permissions "update"
	setup_service
	complete_installation
}

function git_update {
	echo -e "\n${GREEN}Starting Git-based update...${NC}"
	systemctl stop ${APP_NAME}.service
	install_dependencies "nogit"
	update_application "git"
	set_permissions "update"
	setup_service
	complete_installation
}

while true; do
    show_pickle_art
    show_menu
    read -r choice
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
			standard_update
			break
			;;
		4)
			git_update
			break
			;;
		5)
			dry_run_check
			exit 0
			;;
        6)
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
