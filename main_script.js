let switchesPerPage = 15;
let currentSortColumn = -1;
let sortDirection = 1;
let currentPage = 1;
let allSwitches = [];
let filteredSwitches = [];

// Variabili globali per il confronto
let currentCompareSearchTerm = '';
let currentCompareFilters = {
    showAdded: true,
    showRemoved: true,
    showChanged: true,
    showUnchanged: true
};

window.eval = function() {
    throw new Error("eval() is disabled for security reasons");
};

// Funzione di utilità per escape HTML
function escapeHtml(unsafe) {
    return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function changeItemsPerPage() {
    const select = document.getElementById('items-per-page');
    switchesPerPage = parseInt(select.value);
    currentPage = 1; // Resetta alla prima pagina quando cambi il numero di elementi
    renderSwitches();
    updatePagination();
}

function safeInsert(text) {
    return text.replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function filterSwitches() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();

    if (searchTerm.trim() === '') {
        filteredSwitches = [...allSwitches];
    } else {
        filteredSwitches = allSwitches.filter(sw => 
            sw.hostname.toLowerCase().includes(searchTerm) || 
            sw.ip.toLowerCase().includes(searchTerm) ||
            (sw.username && sw.username.toLowerCase().includes(searchTerm)) ||
            sw.device_type.toLowerCase().includes(searchTerm)
        );
    }

    currentPage = 1; // Resetta alla prima pagina quando filtri
    renderSwitches();
    updatePagination();
}


function renderSwitches() {
    const tbody = document.getElementById('switch-table-tbody');
    tbody.innerHTML = '';

    if (filteredSwitches.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No matching devices found</td></tr>';
        return;
    }

    const startIndex = (currentPage - 1) * switchesPerPage;
    const endIndex = Math.min(startIndex + switchesPerPage, filteredSwitches.length);
    const switchesToShow = filteredSwitches.slice(startIndex, endIndex);

    switchesToShow.forEach((sw, i) => {
    const row = document.createElement('tr');
    row.innerHTML = `
<td>
<span class="backup-status" id="status-${sw.originalIndex}" title="${getStatusTooltip(sw)}">
<i class="fas fa-circle" style="color: ${getStatusColor(sw)}; font-size: 10px; margin-right: 5px;"></i>
</span>
${highlightMatches(sw.hostname)}
</td>
<td>${highlightMatches(sw.ip)}</td>
<td>${highlightMatches(sw.username)}</td>
<td>${highlightMatches(sw.device_type)}</td>
<td>
<button class="action-btn backup-btn" title="Backup" onclick="backupSwitch(${sw.originalIndex})">
<i class="fas fa-download"></i>
</button>
<button class="action-btn edit-btn" title="Modifica" onclick="openEditModal(${sw.originalIndex})">
<i class="fas fa-edit"></i>
</button>
<button class="action-btn view-btn" title="Visualizza Backup" onclick="openBackupListModal(${sw.originalIndex})">
<i class="fas fa-eye"></i>
</button>
<button class="action-btn delete-btn" title="Elimina" onclick="deleteSwitch(${sw.originalIndex})">
<i class="fas fa-trash"></i>
</button>
</td>
    `;
    tbody.appendChild(row);
    });
}

function getStatusColor(switchData) {
    if (!switchData.last_backup_status) return 'gray'; // mai eseguito
    if (switchData.last_backup_status === 'success') return 'green'; //backup ok
    if (switchData.last_backup_status === 'failed') return 'red'; // backup fallito
    return 'gray';
}

function getStatusTooltip(switchData) {
    if (!switchData.last_backup_status) return 'Backup never attempted';

    if (switchData.last_backup_status === 'success') 
    return `Last successful backup: ${switchData.last_backup_time}`;

    if (switchData.last_backup_status === 'failed') 
    return `Last backup failed: ${switchData.last_backup_time}`;

    return 'Unknown status';
}



function highlightMatches(text) {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();

    if (!text) return ''; // Aggiunto controllo per valori null/undefined
    if (!searchTerm || !text) return text;

    const str = text.toString();
    const lowerStr = str.toLowerCase();
    const termLower = searchTerm.toLowerCase();

    let result = '';
    let lastIndex = 0;
    let index = lowerStr.indexOf(termLower);

    while (index >= 0) {
        result += str.substring(lastIndex, index) + 
        '<span style="background-color: yellow;">' + 
        str.substring(index, index + searchTerm.length) + 
        '</span>';

        lastIndex = index + searchTerm.length;
        index = lowerStr.indexOf(termLower, lastIndex);
    }

    result += str.substring(lastIndex);
    return result;
}

function updatePagination() {
    const pageCount = Math.ceil(filteredSwitches.length / switchesPerPage);
    const paginationDiv = document.getElementById('pagination');
    paginationDiv.innerHTML = '';

    // Aggiorna la selezione nel menu a tendina
    document.getElementById('items-per-page').value = switchesPerPage;

    // Funzione per pulire tutti gli stati attivi
    const clearActiveStates = () => {
        document.querySelectorAll('#pagination button').forEach(b => {
            b.classList.remove('active');
            b.disabled = false;
        });
    };

    // Pulsante "Indietro"
    const prevBtn = document.createElement('button');
    prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevBtn.disabled = currentPage === 1;

    prevBtn.onclick = () => {
        if (currentPage > 1) {
            clearActiveStates();
            currentPage--;
            renderSwitches();
            updatePagination();
        }
    };

    paginationDiv.appendChild(prevBtn);

    // Pulsanti numerici
    for (let i = 1; i <= pageCount; i++) {
        const btn = document.createElement('button');
        btn.textContent = i;

        btn.onclick = () => {
            clearActiveStates();
            currentPage = i;
            btn.classList.add('active');
            btn.disabled = true;
            renderSwitches();
            updatePagination();
        };

        if (i === currentPage) {
            btn.classList.add('active');
            btn.disabled = true;
        }

        paginationDiv.appendChild(btn);
    }

    // Pulsante "Avanti"
    const nextBtn = document.createElement('button');
    nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextBtn.disabled = currentPage >= pageCount;

    nextBtn.onclick = () => {
        if (currentPage < pageCount) {
            clearActiveStates();
            currentPage++;
            renderSwitches();
            updatePagination();
        }
    };

    paginationDiv.appendChild(nextBtn);

    if (pageCount === 0) {
        paginationDiv.innerHTML = '<span>No devices found</span>';
    }
}

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

    // Ordina filteredSwitches invece di fare una nuova richiesta
    filteredSwitches.sort((a, b) => {
        const keys = ['hostname', 'ip', 'username', 'device_type'];
        const key = keys[columnIndex];
        const valA = a[key]?.toLowerCase() || '';
        const valB = b[key]?.toLowerCase() || '';

        if (valA < valB) return -1 * sortDirection;
        if (valA > valB) return 1 * sortDirection;

        return 0;
    });

    currentPage = 1; // Resetta alla prima pagina quando si ordina
    renderSwitches();
    updatePagination();
    updateSortIcons();
}

function updateSwitchTable() {
    fetch('/get_switches')
    .then(response => response.json())
    .then(switchesData => {
        allSwitches = switchesData.map((sw, index) => ({...sw, originalIndex: index}));
        filteredSwitches = [...allSwitches];

        renderSwitches();
        updatePagination();
        updateSortIcons();

        filterSwitches();
    })
    .catch(error => {
        console.error('Device load failed:', error);
        const tbody = document.getElementById('switch-table-tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: red;">Error during the device update</td></tr>';
    });
}

function toggleSearchIcon() {
    const searchInput = document.getElementById('search-input');
    const searchIcon = document.getElementById('search-icon');

    if (searchInput.value.length > 0) {
        searchIcon.classList.remove('fa-search');
        searchIcon.classList.add('fa-times');
    } else {
        searchIcon.classList.remove('fa-times');
        searchIcon.classList.add('fa-search');
    }
}

function clearSearch() {
    const searchInput = document.getElementById('search-input');
    const searchIcon = document.getElementById('search-icon');

    if (searchIcon.classList.contains('fa-times')) {
        searchInput.value = '';
        searchIcon.classList.remove('fa-times');
        searchIcon.classList.add('fa-search');
        filterSwitches(); // Chiama di nuovo la funzione di filtro per aggiornare la lista
    }
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

function openBackupListModal(index) {
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
            const modal = document.getElementById('backup-list-modal');
            const switchName = document.getElementById('modal-switch-name');
            const backupList = document.getElementById('backup-list');
            const exportAllBtn = document.getElementById('export-all-backup-btn');
            const backupButtonBar = document.getElementById('backup-button-bar');

            switchName.textContent = data.hostname;
            backupList.innerHTML = '';

            // Riempio barra pulsanti con i bottoni, e valorizzo l'index del compare-select-btn
            backupButtonBar.innerHTML = `
<button class="action-btn compare-select-btn" id="compare-select-btn" onclick="openCompareSelectModal(${index})" style="padding: 5px 12px; font-size: 13px;">
<i class="fa-solid fa-code-compare"></i> Compare
</button>
<button class="action-btn backup-btn" id="export-backup-btn" onclick="exportBackup()" style="padding: 5px 12px; font-size: 13px;">
<i class="fas fa-download"></i> Export
</button>
<button class="action-btn delete-btn" id="delete-backup-btn" onclick="deleteBackup()" style="padding: 5px 12px; font-size: 13px;">
<i class="fas fa-trash"></i> Delete
</button>
`
            // Imposta l'indice dello switch sul pulsante Export All
            exportAllBtn.setAttribute('data-switch-index', index);

            if (data.backups.length === 0) {
                backupList.innerHTML = '<p>No available backups</p>';
                exportAllBtn.disabled = true;
                exportAllBtn.title = 'No backups available';
                exportAllBtn.style.opacity = '0.5';
                exportAllBtn.style.cursor = 'not-allowed';
            } else {
                data.backups.forEach(backup => {
                    const backupItem = document.createElement('div');
                    backupItem.className = 'backup-item';
                    backupItem.textContent = backup.filename;
                    backupItem.setAttribute('data-path', backup.path);
                    backupItem.onclick = () => loadBackupContent(backup.path, index);
                    backupList.appendChild(backupItem);
                });

                exportAllBtn.disabled = false;
                exportAllBtn.title = 'Export all backups as ZIP';
                exportAllBtn.style.opacity = '1';
                exportAllBtn.style.cursor = 'pointer';
            }

            document.getElementById('backup-content').style.display = 'none';
            document.getElementById('backup-content-placeholder').style.display = 'block';
            modal.style.display = 'block';
        } else {
            showStatus('Error: ' + data.message, 'error');
        }
    });

    document.addEventListener('keydown', handleEscConfigModal);
}

function loadBackupContent(filepath, switchIndex) {
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
            const configContent = document.querySelector('#backup-content .config-content');
            const compareBtn = document.getElementById('compare-select-btn');
            const exportBtn = document.getElementById('export-backup-btn');
            const deleteBtn = document.getElementById('delete-backup-btn');

            configContent.textContent = ""
            configContent.textContent = data.content;

            contentDiv.style.display = 'flex';
            placeholder.style.display = 'none';
            compareBtn.style.display = 'inline-block';
            exportBtn.style.display = 'inline-block';
            deleteBtn.style.display = 'inline-block';
            deleteBtn.setAttribute('data-filepath', filepath);
            deleteBtn.setAttribute('data-switch-index', switchIndex);

            // Evidenzio il backup selezionato nella lista
            document.querySelectorAll('.backup-item').forEach(item => {
                item.classList.toggle('active', item.textContent.includes(data.filename));
            });
        } else {
            const configContent = document.querySelector('#backup-content .config-content');
            configContent.textContent = "File not found!";
        }
    });
}

function openCompareSelectModal(index) {
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
            const modal = document.getElementById('compare-select-modal');
            const switchName = document.getElementById('compare-select-switch-name');
            const compareBackupList = document.getElementById('compare-backup-list');
            const compareConfirmBtn = document.getElementById('compare-confirm-btn');

            switchName.textContent = data.hostname;
            compareBackupList.innerHTML = '';

            // Prendo source file path dalla modal precedente, e lo 
            // imposto su bottone Compare
            const deleteBtn = document.getElementById('delete-backup-btn');
            sourceFilePath = deleteBtn.getAttribute('data-filepath');
            // debug command
            //alert(sourceFilePath);
            compareConfirmBtn.setAttribute('source-file-path', sourceFilePath);
            compareConfirmBtn.setAttribute('compare-device-name', data.hostname);

            data.backups.forEach(backup => {
                const compareBackupItem = document.createElement('div');
                compareBackupItem.className = 'backup-item';
                compareBackupItem.textContent = backup.filename;
                compareBackupItem.setAttribute('data-path', backup.path);
                compareBackupItem.onclick = () => loadCompareSelectedBackupContent(backup.path, index);
                compareBackupList.appendChild(compareBackupItem);
            });

            compareConfirmBtn.disabled = false;
            compareConfirmBtn.title = 'Compare the configuration';
            compareConfirmBtn.style.opacity = '1';
            compareConfirmBtn.style.cursor = 'pointer';
            
            modal.style.display = 'block';
        } else {
            showStatus('Error: ' + data.message, 'error');
        }
    });

    document.addEventListener('keydown', handleEscCompareSelectModal);
}

function loadCompareSelectedBackupContent(filepath, switchIndex) {
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
            const compareConfirmBtn = document.getElementById('compare-confirm-btn');
            const contentDiv = document.getElementById('compare-backup-content');
            const placeholder = document.getElementById('compare-backup-content-placeholder');
            const configContent = document.querySelector('#compare-backup-content .config-content');
            /*const compareBtn = document.getElementById('compare-select-btn');
            const exportBtn = document.getElementById('export-backup-btn');
            const deleteBtn = document.getElementById('delete-backup-btn');*/

            configContent.textContent = data.content;

            contentDiv.style.display = 'flex';
            placeholder.style.display = 'none';
            /*compareBtn.style.display = 'inline-block';
            exportBtn.style.display = 'inline-block';
            deleteBtn.style.display = 'inline-block';
            deleteBtn.setAttribute('data-filepath', filepath);
            deleteBtn.setAttribute('data-switch-index', switchIndex);*/
            
            // debug command
            //alert(filepath);
            compareConfirmBtn.setAttribute('compare-file-path', filepath);

            //debug command
            //alert('Dovrò confrontare il \n' + compareConfirmBtn.getAttribute('source-file-path') + '\n con il \n' + compareConfirmBtn.getAttribute('compare-file-path'));

            // Evidenzio il backup selezionato nella lista
            document.querySelectorAll('.backup-item').forEach(item => {
                item.classList.toggle('active', item.textContent.includes(data.filename));
            });
        } else {
            const configContent = document.querySelector('#compare-backup-content .config-content');
            configContent.textContent = "File not found!";
        }
    });
}

function fetchBackupContent(filepath) {
    return fetch('/get_backup_content', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ filepath }),
    }).then(response => response.json());
}

/*
function setupSyncScroll() {
    const leftPanel = document.getElementById('left-config-content');
    const rightPanel = document.getElementById('right-config-content');
    const diffPanel = document.getElementById('diff-content');
    
    // Funzione per sincronizzare lo scroll
    const syncScroll = (source, target1, target2) => {
        if (source.syncing) return;
        source.syncing = true;
        
        target1.scrollTop = source.scrollTop;
        target2.scrollTop = source.scrollTop;
        
        setTimeout(() => { source.syncing = false; }, 1);
    };
    
    // Aggiungi gli event listeners per lo scroll
    leftPanel.addEventListener('scroll', () => syncScroll(leftPanel, rightPanel, diffPanel));
    rightPanel.addEventListener('scroll', () => syncScroll(rightPanel, leftPanel, diffPanel));
    diffPanel.addEventListener('scroll', () => syncScroll(diffPanel, leftPanel, rightPanel));
}*/

function setupSyncScroll() {
    const leftPanel = document.getElementById('left-config-content');
    const rightPanel = document.getElementById('right-config-content');
    
    const syncScroll = (source, target) => {
        if (source.syncing) return;
        source.syncing = true;
        target.scrollTop = source.scrollTop;
        setTimeout(() => { source.syncing = false; }, 1);
    };
    
    leftPanel.addEventListener('scroll', () => syncScroll(leftPanel, rightPanel));
    rightPanel.addEventListener('scroll', () => syncScroll(rightPanel, leftPanel));
}

/*
function compareConfigurations(sourceContent, compareContent) {
    // Dividi i contenuti in righe
    const sourceLines = sourceContent.split('\n');
    const compareLines = compareContent.split('\n');
    
    // Usa un algoritmo diff per trovare le differenze
    const diff = Diff.diffLines(sourceContent, compareContent);
    
    // Prepara i contenuti per la visualizzazione
    let leftHtml = '';
    let rightHtml = '';
    let diffHtml = '';
    let leftLineNum = 1;
    let rightLineNum = 1;
    
    diff.forEach(part => {
        const lines = part.value.split('\n');
        lines.pop(); // Rimuovi l'ultima riga vuota
        
        if (part.added) {
            // Righe aggiunte (solo nel file di destra)
            lines.forEach(line => {
                rightHtml += `<div class="config-line added-line">
                    <span class="line-number">${rightLineNum++}</span>${escapeHtml(line)}
                </div>`;
                diffHtml += `<div class="diff-marker diff-added">+</div>`;
            });
        } else if (part.removed) {
            // Righe rimosse (solo nel file di sinistra)
            lines.forEach(line => {
                leftHtml += `<div class="config-line removed-line">
                    <span class="line-number">${leftLineNum++}</span>${escapeHtml(line)}
                </div>`;
                diffHtml += `<div class="diff-marker diff-removed">-</div>`;
            });
        } else {
            // Righe uguali in entrambi i file
            lines.forEach(line => {
                leftHtml += `<div class="config-line same-line">
                    <span class="line-number">${leftLineNum++}</span>${escapeHtml(line)}
                </div>`;
                rightHtml += `<div class="config-line same-line">
                    <span class="line-number">${rightLineNum++}</span>${escapeHtml(line)}
                </div>`;
                diffHtml += `<div class="diff-marker diff-empty">&equals;</div>`;
            });
        }
    });
    
    // Inserisci i contenuti nei rispettivi pannelli
    document.getElementById('left-config-content').innerHTML = leftHtml;
    document.getElementById('right-config-content').innerHTML = rightHtml;
    document.getElementById('diff-content').innerHTML = diffHtml;
    
    // Aggiungi lo scroll sincronizzato
    setupSyncScroll();
}*/

/*
function compareConfigurations(sourceContent, compareContent) {
    // Dividi i contenuti in righe
    const sourceLines = sourceContent.split('\n');
    const compareLines = compareContent.split('\n');
    
    // Usa un algoritmo diff per trovare le differenze
    const diff = Diff.diffLines(sourceContent, compareContent);
    
    // Statistiche
    let stats = {
        added: 0,
        removed: 0,
        changed: 0,
        unchanged: 0,
        total: 0
    };
    
    // Prepara i contenuti per la visualizzazione
    let leftHtml = '';
    let rightHtml = '';
    let diffHtml = '';
    let leftLineNum = 1;
    let rightLineNum = 1;
    
    diff.forEach(part => {
        const lines = part.value.split('\n');
        lines.pop(); // Rimuovi l'ultima riga vuota
        
        if (part.added) {
            // Righe aggiunte (solo nel file di destra)
            stats.added += lines.length;
            stats.total += lines.length;
            
            lines.forEach(line => {
                const lineClass = currentCompareFilters.showAdded ? 'added-line' : 'hidden-line';
                rightHtml += `<div class="config-line ${lineClass}" data-line-type="added">
                    <span class="line-number">${rightLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
                diffHtml += `<div class="diff-marker ${currentCompareFilters.showAdded ? 'diff-added' : 'hidden-line'}" data-line-type="added">+</div>`;
            });
        } else if (part.removed) {
            // Righe rimosse (solo nel file di sinistra)
            stats.removed += lines.length;
            stats.total += lines.length;
            
            lines.forEach(line => {
                const lineClass = currentCompareFilters.showRemoved ? 'removed-line' : 'hidden-line';
                leftHtml += `<div class="config-line ${lineClass}" data-line-type="removed">
                    <span class="line-number">${leftLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
                diffHtml += `<div class="diff-marker ${currentCompareFilters.showRemoved ? 'diff-removed' : 'hidden-line'}" data-line-type="removed">-</div>`;
            });
        } else {
            // Righe uguali in entrambi i file
            stats.unchanged += lines.length;
            stats.total += lines.length;
            
            lines.forEach(line => {
                const lineClass = currentCompareFilters.showUnchanged ? 'same-line' : 'hidden-line';
                leftHtml += `<div class="config-line ${lineClass}" data-line-type="unchanged">
                    <span class="line-number">${leftLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
                rightHtml += `<div class="config-line ${lineClass}" data-line-type="unchanged">
                    <span class="line-number">${rightLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
                diffHtml += `<div class="diff-marker ${currentCompareFilters.showUnchanged ? 'diff-empty' : 'hidden-line'}" data-line-type="unchanged">=</div>`;
            });
        }
    });
    
    // Inserisci i contenuti nei rispettivi pannelli
    document.getElementById('left-config-content').innerHTML = leftHtml;
    document.getElementById('right-config-content').innerHTML = rightHtml;
    document.getElementById('diff-content').innerHTML = diffHtml;
    
    // Aggiorna le statistiche
    updateCompareStats(stats);
    
    // Aggiungi lo scroll sincronizzato
    setupSyncScroll();
    
    // Aggiungi la barra di ricerca
    addCompareSearchBar();
    
    // Aggiungi i filtri
    addCompareFilters();
    
    // Se c'è un termine di ricerca, applicalo
    if (currentCompareSearchTerm) {
        highlightSearchMatches(currentCompareSearchTerm);
    }
}*/

function compareConfigurations(sourceContent, compareContent) {
    const diff = Diff.diffLines(sourceContent, compareContent);
    
    let stats = {
        added: 0,
        removed: 0,
        unchanged: 0,
        total: 0
    };
    
    let leftHtml = '';
    let rightHtml = '';
    let leftLineNum = 1;
    let rightLineNum = 1;
    
    diff.forEach(part => {
        const lines = part.value.split('\n');
        lines.pop();
        
        if (part.added) {
            stats.added += lines.length;
            lines.forEach(line => {
                const visible = currentCompareFilters.showAdded ? '' : 'hidden-line';
                rightHtml += `<div class="config-line added-line ${visible}" data-line-type="added">
                    <span class="line-number">${rightLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
            });
        } else if (part.removed) {
            stats.removed += lines.length;
            lines.forEach(line => {
                const visible = currentCompareFilters.showRemoved ? '' : 'hidden-line';
                leftHtml += `<div class="config-line removed-line ${visible}" data-line-type="removed">
                    <span class="line-number">${leftLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
            });
        } else {
            stats.unchanged += lines.length;
            lines.forEach(line => {
                const visible = currentCompareFilters.showUnchanged ? '' : 'hidden-line';
                leftHtml += `<div class="config-line same-line ${visible}" data-line-type="unchanged">
                    <span class="line-number">${leftLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
                rightHtml += `<div class="config-line same-line ${visible}" data-line-type="unchanged">
                    <span class="line-number">${rightLineNum++}</span>
                    <span class="line-content">${escapeHtml(line)}</span>
                </div>`;
            });
        }
    });
    
    stats.total = stats.added + stats.removed + stats.unchanged;
    
    document.getElementById('left-config-content').innerHTML = leftHtml;
    document.getElementById('right-config-content').innerHTML = rightHtml;
    updateCompareStats(stats);
    setupSyncScroll();
    
    if (currentCompareSearchTerm) {
        highlightSearchMatches(currentCompareSearchTerm);
    }
}

function updateCompareStats(stats) {
    const statsHtml = `
        <div><strong>Total lines:</strong> ${stats.total}</div>
        <div><span style="color:#4caf50">Added:</span> ${stats.added}</div>
        <div><span style="color:#f44336">Removed:</span> ${stats.removed}</div>
        <div><span style="color:#ffc107">Changed:</span> ${stats.changed}</div>
        <div><span style="color:#777">Unchanged:</span> ${stats.unchanged}</div>
    `;
    
    let statsDiv = document.getElementById('compare-stats');
    if (!statsDiv) {
        statsDiv = document.createElement('div');
        statsDiv.id = 'compare-stats';
        statsDiv.className = 'compare-stats';
        document.querySelector('.compare-container').appendChild(statsDiv);
    }
    statsDiv.innerHTML = statsHtml;
}

function addCompareSearchBar() {
    let searchBar = document.getElementById('compare-search-bar');
    if (!searchBar) {
        searchBar = document.createElement('div');
        searchBar.id = 'compare-search-bar';
        searchBar.className = 'compare-search';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search in config...';
        searchInput.id = 'compare-search-input';
        
        const searchButton = document.createElement('button');
        searchButton.textContent = 'Search';
        searchButton.onclick = () => {
            currentCompareSearchTerm = document.getElementById('compare-search-input').value;
            highlightSearchMatches(currentCompareSearchTerm);
        };
        
        searchBar.appendChild(searchInput);
        searchBar.appendChild(searchButton);
        document.querySelector('.compare-container').appendChild(searchBar);
    }
}   

function addCompareFilters() {
    let filtersDiv = document.getElementById('compare-filters');
    if (!filtersDiv) {
        filtersDiv = document.createElement('div');
        filtersDiv.id = 'compare-filters';
        filtersDiv.className = 'compare-filters';
        
        const filters = [
            { id: 'filter-added', label: 'Show added lines', type: 'showAdded', color: '#4caf50' },
            { id: 'filter-removed', label: 'Show removed lines', type: 'showRemoved', color: '#f44336' },
            { id: 'filter-changed', label: 'Show changed lines', type: 'showChanged', color: '#ffc107' },
            { id: 'filter-unchanged', label: 'Show unchanged lines', type: 'showUnchanged', color: '#777' }
        ];
        
        filters.forEach(filter => {
            const label = document.createElement('label');
            
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.id = filter.id;
            input.checked = currentCompareFilters[filter.type];
            input.onchange = () => {
                currentCompareFilters[filter.type] = input.checked;
                applyCompareFilters();
            };
            
            const span = document.createElement('span');
            span.textContent = filter.label;
            span.style.color = filter.color;
            
            label.appendChild(input);
            label.appendChild(span);
            filtersDiv.appendChild(label);
        });
        
        document.querySelector('.compare-container').appendChild(filtersDiv);
    }
}

/*
function applyCompareFilters() {
    const leftPanel = document.getElementById('left-config-content');
    const rightPanel = document.getElementById('right-config-content');
    const diffPanel = document.getElementById('diff-content');
    
    // Aggiorna la visibilità delle righe in base ai filtri
    document.querySelectorAll('.config-line').forEach(line => {
        const lineType = line.getAttribute('data-line-type');
        line.style.display = currentCompareFilters[`show${lineType.charAt(0).toUpperCase() + lineType.slice(1)}`] ? '' : 'none';
    });
    
    document.querySelectorAll('.diff-marker').forEach(marker => {
        const lineType = marker.getAttribute('data-line-type');
        marker.style.display = currentCompareFilters[`show${lineType.charAt(0).toUpperCase() + lineType.slice(1)}`] ? '' : 'none';
    });
    
    // Ricalcola le statistiche
    const stats = {
        added: 0,
        removed: 0,
        changed: 0,
        unchanged: 0,
        total: 0
    };
    
    document.querySelectorAll('.config-line').forEach(line => {
        if (line.style.display !== 'none') {
            const lineType = line.getAttribute('data-line-type');
            stats[lineType]++;
            stats.total++;
        }
    });
    
    updateCompareStats(stats);
}*/

function applyCompareFilters() {
    document.querySelectorAll('.config-line').forEach(line => {
        const lineType = line.getAttribute('data-line-type');
        const shouldShow = currentCompareFilters[`show${lineType.charAt(0).toUpperCase() + lineType.slice(1)}`];
        line.style.display = shouldShow ? '' : 'none';
    });
    
    // Aggiorna stats
    const stats = {
        added: 0,
        removed: 0,
        unchanged: 0,
        total: 0
    };
    
    document.querySelectorAll('.config-line').forEach(line => {
        if (line.style.display !== 'none') {
            const lineType = line.getAttribute('data-line-type');
            stats[lineType]++;
            stats.total++;
        }
    });
    
    updateCompareStats(stats);
}

function highlightSearchMatches(searchTerm) {
    // Rimuovi evidenziazioni precedenti
    document.querySelectorAll('.search-match').forEach(el => {
        el.classList.remove('search-match');
    });
    
    if (!searchTerm) return;
    
    const regex = new RegExp(escapeRegExp(searchTerm), 'gi');
    let matchCount = 0;
    
    // Evidenzia nei pannelli sinistro e destro
    document.querySelectorAll('.line-content').forEach(contentEl => {
        const lineEl = contentEl.closest('.config-line');
        if (lineEl.style.display !== 'none') {
            const text = contentEl.textContent;
            const highlighted = text.replace(regex, match => `<span class="search-match">${match}</span>`);
            if (highlighted !== text) {
                contentEl.innerHTML = highlighted;
                lineEl.classList.add('highlighted-line');
                matchCount++;
            }
        }
    });
    
    // Mostra il numero di corrispondenze
    const statsDiv = document.getElementById('compare-stats');
    if (statsDiv) {
        const matchInfo = document.createElement('div');
        matchInfo.innerHTML = `<div><strong>Search matches:</strong> ${matchCount}</div>`;
        statsDiv.appendChild(matchInfo);
    }
    
    // Scorri alla prima corrispondenza
    const firstMatch = document.querySelector('.highlighted-line');
    if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/*
function openCompareModal(sourcePath, comparePath, deviceName) {
    // show loading status
    showStatus('Preparing configuration comparison...', 'success');

    Promise.all([
        fetchBackupContent(sourcePath),
        fetchBackupContent(comparePath)
    ]).then(([sourceData, compareData]) => {
        if (sourceData.success && compareData.success) {
            // Estrai i nomi dei file dai percorsi
            const sourceName = sourcePath.split('/').pop();
            const compareName = comparePath.split('/').pop();
            const comparisonDeviceName = document.getElementById('comparison-switch-name');

            // Imposta i titoli
            comparisonDeviceName.textContent = deviceName;
            document.getElementById('left-file-info').textContent = sourceName;
            document.getElementById('right-file-info').textContent = compareName;
            
            // Confronta i contenuti
            compareConfigurations(sourceData.content, compareData.content);
            
            // Mostra la modal
            document.getElementById('config-compare-modal').style.display = 'block';
            document.addEventListener('keydown', handleEscCompareModal);
        } else {
            showStatus('Error loading configurations for comparison', 'error');
        }
    }).catch(error => {
        showStatus('Comparison error: ' + error, 'error');
    });
}*/

function openCompareModal(sourcePath, comparePath, deviceName) {
    // show loading status
    showStatus('Preparing configuration comparison...', 'success');

    Promise.all([
        fetchBackupContent(sourcePath),
        fetchBackupContent(comparePath)
    ]).then(([sourceData, compareData]) => {
        if (sourceData.success && compareData.success) {
            // Estrai i nomi dei file dai percorsi
            const sourceName = sourcePath.split('/').pop();
            const compareName = comparePath.split('/').pop();
            const comparisonDeviceName = document.getElementById('comparison-switch-name');

            // Imposta i titoli
            comparisonDeviceName.textContent = deviceName;
            document.getElementById('left-file-info').textContent = sourceName;
            document.getElementById('right-file-info').textContent = compareName;
            
            // Confronta i contenuti
            compareConfigurations(sourceData.content, compareData.content);
            
            // Mostra la modal
            document.getElementById('config-compare-modal').style.display = 'block';
            document.addEventListener('keydown', handleEscCompareModal);
            
            // Aggiungi gestione ricerca con tasto Invio
            document.getElementById('compare-search-input')?.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    currentCompareSearchTerm = document.getElementById('compare-search-input').value;
                    highlightSearchMatches(currentCompareSearchTerm);
                }
            });
        } else {
            showStatus('Error loading configurations for comparison', 'error');
        }
    }).catch(error => {
        showStatus('Comparison error: ' + error, 'error');
    });
}

// Modifica la funzione startConfigurationCompare per utilizzare la nuova modal
function startConfigurationCompare() {
    const compareConfirmBtn = document.getElementById('compare-confirm-btn');

    const sourcePath = compareConfirmBtn.getAttribute('source-file-path');
    const comparePath = compareConfirmBtn.getAttribute('compare-file-path');
    const deviceName = compareConfirmBtn.getAttribute('compare-device-name');
    
    if (!sourcePath || !comparePath) {
        showStatus('Please select both configurations to compare', 'error');
        return;
    }
    
    closeCompareSelectModal();
    openCompareModal(sourcePath, comparePath, deviceName);
}

function exportAllBackup() {
    const backupItems = document.querySelectorAll('.backup-item');
    if (backupItems.length === 0) {
        showStatus('No backups available for export', 'error');
        return;
    }

    const switchName = document.getElementById('modal-switch-name').textContent.trim();
    showStatus('Preparing all backups for export...', 'success');

    // Recupera tutti i percorsi dei backup dalla lista già caricata
    const backups = [];
    backupItems.forEach(item => {
        backups.push({
            filename: item.textContent,
            path: item.getAttribute('data-path') || ''
        });
    });

    // Chiamata al backend per creare lo ZIP
    fetch('/export_all_backups', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ 
            backups: backups,
            hostname: switchName
        }),
    })
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${switchName}_all_backups_${new Date().toISOString().slice(0, 10)}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showStatus(`All backups exported successfully`, 'success');
    })
    .catch(error => {
        showStatus('Export failed: ' + error, 'error');
    });
}

function exportBackup() {
    const configContent = document.querySelector('#backup-content .config-content').textContent;
    const filename = document.querySelector('.backup-item.active').textContent;

    // Crea un blob con il contenuto
    const blob = new Blob([configContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    // Crea un link temporaneo e simula il click
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    // Pulisci
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showStatus('Backup exported successfully', 'success');
    addToLog(`Exported backup: ${filename}`);
}

function deleteBackup() {
    const currentBackupPath = document.getElementById('delete-backup-btn').getAttribute('data-filepath');
    if (!currentBackupPath) return;

    if (!confirm('Are you sure you want to delete this backup? This action cannot be undone.')) {
        return;
    }

    fetch('/delete_backup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ filepath: currentBackupPath }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('Backup deleted successfully', 'success');
            addToLog(`Deleted backup: ${currentBackupPath}`);
            closeConfigModal();
            // Se stavi visualizzando i backup di uno switch specifico, potresti voler ricaricare la lista
            const currentSwitchIndex = document.getElementById('delete-backup-btn').getAttribute('data-switch-index');

            if (currentSwitchIndex) {
                openBackupListModal(currentSwitchIndex);
            }
        } else {
            showStatus('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showStatus('Connection error: ' + error, 'error');
    });
}

function copyToClipboard(element) {
    const configContent = element.querySelector('pre').textContent;
    navigator.clipboard.writeText(configContent).then(() => {
        const tooltip = element.querySelector('.tooltiptext');
        tooltip.textContent = '✓ Copied!';
        element.classList.add('copied');

        setTimeout(() => {
            tooltip.textContent = 'Copy to clipboard';
            element.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        element.querySelector('.tooltiptext').textContent = '✗ Failed to copy!';
    });
}

function closeConfigModal() {
    document.getElementById('backup-list-modal').style.display = 'none';
    document.getElementById('compare-select-btn').style.display = 'none';
    document.getElementById('export-backup-btn').style.display = 'none';
    document.getElementById('delete-backup-btn').style.display = 'none';

    document.removeEventListener('keydown', handleEscConfigModal);
}

function closeCompareSelectModal() {
    document.getElementById('compare-select-modal').style.display = 'none';
    document.removeEventListener('keydown', handleEscCompareSelectModal);
}

function closeCompareModal() {
    document.getElementById('config-compare-modal').style.display = 'none';
    document.removeEventListener('keydown', handleEscCompareModal);
}

function openEditModal(index) {
    fetch('/get_switches')
    .then(response => response.json())
    .then(switchesData => {
        if (index >= 0 && index < switchesData.length) {
            const switchData = switchesData[index];

            document.getElementById('edit-hostname').value = switchData.hostname;
            document.getElementById('edit-ip').value = switchData.ip;
            document.getElementById('edit-device-type').value = switchData.device_type;
            document.getElementById('edit-username').value = switchData.username;
            document.getElementById('edit-password').value = '';
            document.getElementById('edit-enable-password').value = '';
            document.getElementById('edit-index').value = index;

            document.getElementById('edit-modal').style.display = 'block';
        }
    });

    document.addEventListener('keydown', handleEscEditModal);
}

function saveEditedSwitch() {
    const index = document.getElementById('edit-index').value;
    const hostname = document.getElementById('edit-hostname').value;
    const ip = document.getElementById('edit-ip').value;
    const username = document.getElementById('edit-username').value;
    const password = document.getElementById('edit-password').value;
    const enablePassword = document.getElementById('edit-enable-password').value;
    const deviceType = document.getElementById('edit-device-type').value;

    if (!hostname || !ip || !username) {
        showStatus('Please fill all required fields', 'error');
        return;
    }

    const switchData = {
        index: parseInt(index),
        hostname: hostname,
        ip: ip,
        username: username,
        device_type: deviceType
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
        // salvo elenco switch, aggiorno tabella switch e schedule, e ripristino eventuale ricerca
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
    document.removeEventListener('keydown', handleEscEditModal);
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

function colorLogLine(line) {
    const lowerLine = line.toLowerCase();
    if (lowerLine.includes('error') || lowerLine.includes('failed')) {
        return `<div class="log-line error">${line}</div>`;
    } else if (lowerLine.includes('warning')) {
        return `<div class="log-line warning">${line}</div>`;
    } else if (lowerLine.includes('success') || lowerLine.includes('completed')) {
        return `<div class="log-line success">${line}</div>`;
    }

    return `<div class="log-line">${line}</div>`;
}

function openLogModal() {
    fetch('/get_full_log')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const modal = document.getElementById('log-modal');
            const logContent = document.getElementById('full-log-content');

            // Pulisci e formatta il log
            const lines = data.log.match(/[^\r\n]+/g) || [];
            logContent.innerHTML = lines
            .filter(line => line.trim())
            .map(line => `<div class="log-line">${line}</div>`)
            .join('');

            modal.style.display = 'block';
        } else {
            showStatus('Error: ' + data.message, 'error');
        }
    });

    document.addEventListener('keydown', handleEscLogModal);
}

function closeLogModal() {
    document.getElementById('log-modal').style.display = 'none';
    document.removeEventListener('keydown', handleEscLogModal);
}

window.onclick = function(event) {
    const backupModal = document.getElementById('backup-list-modal');
    const editModal = document.getElementById('edit-modal');
    const logModal = document.getElementById('log-modal');
    const compareselectModal = document.getElementById('compare-select-modal');

    if (event.target === backupModal) {
        backupModal.style.display = 'none';
    }
    if (event.target === editModal) {
        editModal.style.display = 'none';
    }
    if (event.target === logModal) {
        logModal.style.display = 'none';
    }
    if (event.target === compareselectModal) {
        compareselectModal.style.display = 'none';
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

function setupModalCloseOnEsc() {
    // Chiudi modali quando si preme ESC
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            // Chiudi modale modifica switch
            const editModal = document.getElementById('editSwitchModal');
            if (editModal && editModal.style.display === 'block') {
                closeEditModal();
            }

            // Chiudi modale visualizzazione log
            const logModal = document.getElementById('viewLogModal');
            if (logModal && logModal.style.display === 'block') {
                closeLogModal();
            }

            // Chiudi modale visualizzazione configurazione
            const configModal = document.getElementById('viewConfigModal');
            if (configModal && configModal.style.display === 'block') {
                closeConfigModal();
            }
        }
    });
}

function handleEscEditModal(event) {
    if (event.key === 'Escape') {
        closeEditModal();
    }
}

function handleEscLogModal(event) {
    if (event.key === 'Escape') {
        closeLogModal();
    }
}

function handleEscConfigModal(event) {
    if (event.key === 'Escape') {
        closeConfigModal();
    }
}

function handleEscCompareSelectModal(event) {
    if (event.key === 'Escape') {
        closeCompareSelectModal();
    }
}

function handleEscCompareModal(event) {
    if (event.key === 'Escape') {
        closeCompareModal();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateSwitchTable();
    showScheduleOptions();
    updateSchedulesList();

    const today = new Date().toISOString().split('T')[0];
    document.getElementById('schedule-date').min = today;
    document.getElementById('schedule-date').value = today;
});

window.addEventListener('DOMContentLoaded', function() {
    setupModalCloseOnEsc();
});

document.addEventListener('DOMContentLoaded', function() {
    toggleSearchIcon();
});

$(document).ready(function() {
    $('select').select2({
        width: '100%',
        dropdownAutoWidth: true,
        theme: 'default'
    });
    $('#device-type, #edit-device-type').select2({
        width: 'resolve', // Usa la larghezza dell'elemento originale
        minimumResultsForSearch: Infinity // Disabilita la ricerca se pochi elementi
    });
});