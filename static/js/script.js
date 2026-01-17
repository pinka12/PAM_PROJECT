// Global variables
let currentPage = 1;
let pageSize = 10;
let totalManagers = 0;
let currentSort = { field: 'last_updated', order: 'desc' };
let currentFilters = {};
let selectedManager = null;
let triangleChart = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadAllData();
    setupEventListeners();
    setupAutoRefresh();
});

// Setup event listeners
function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('search-input');
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentFilters.search = this.value;
            loadManagers();
        }, 500);
    });
    
    // Filter selects
    document.getElementById('assessment-filter').addEventListener('change', function() {
        currentFilters.assessments = this.value;
    });
    
    document.getElementById('score-filter').addEventListener('change', function() {
        currentFilters.score = this.value;
    });
    
    // Pagination buttons
    document.getElementById('prev-page').addEventListener('click', () => changePage(-1));
    document.getElementById('next-page').addEventListener('click', () => changePage(1));
    
    // Enter key in search
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            applyFilters();
        }
    });
}

// Setup auto-refresh every 30 seconds
function setupAutoRefresh() {
    setInterval(() => {
        loadStats();
    }, 30000); // 30 seconds
}

// Load all data initially
async function loadAllData() {
    showLoading('Loading dashboard data...');
    try {
        await Promise.all([
            loadStats(),
            loadManagers(),
            loadHierarchyPreview()
        ]);
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load dashboard data');
    } finally {
        hideLoading();
    }
}

// Refresh all data
async function refreshAllData() {
    showLoading('Refreshing data...');
    try {
        await Promise.all([
            loadStats(),
            loadManagers(),
            loadHierarchyPreview()
        ]);
        showSuccess('Data refreshed successfully');
    } catch (error) {
        console.error('Error refreshing data:', error);
        showError('Failed to refresh data');
    } finally {
        hideLoading();
    }
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) throw new Error('Failed to load stats');
        
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Failed to load stats');
        
        updateStatsDisplay(data);
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('stats-container').innerHTML = `
            <div class="stat-card">
                <h3>Error</h3>
                <p>Failed to load stats</p>
            </div>
        `;
    }
}

// Update stats display
function updateStatsDisplay(data) {
    const stats = data.stats || {};
    const averages = data.averages || {};
    
    const statsHTML = `
        <div class="stat-card">
            <h3>Total Responses</h3>
            <p>${stats.total_responses || 0}</p>
            <div class="stat-trend">
                <i class="fas fa-chart-line"></i>
                <span>${stats.today_responses || 0} today</span>
            </div>
        </div>
        
        <div class="stat-card">
            <h3>Managers Assessed</h3>
            <p>${stats.total_managers || 0}</p>
            <div class="stat-trend">
                <i class="fas fa-user-friends"></i>
                <span>${stats.responses_per_manager || 0} avg/manager</span>
            </div>
        </div>
        
        <div class="stat-card">
            <h3>Avg Trusting Score</h3>
            <p>${averages.trusting || 0}%</p>
            <div class="stat-trend">
                <i class="fas fa-handshake"></i>
                <span>Integrity & Reliability</span>
            </div>
        </div>
        
        <div class="stat-card">
            <h3>Avg Tasking Score</h3>
            <p>${averages.tasking || 0}%</p>
            <div class="stat-trend">
                <i class="fas fa-tasks"></i>
                <span>Planning & Execution</span>
            </div>
        </div>
        
        <div class="stat-card">
            <h3>Avg Tending Score</h3>
            <p>${averages.tending || 0}%</p>
            <div class="stat-trend">
                <i class="fas fa-users"></i>
                <span>Team Development</span>
            </div>
        </div>
        
        <div class="stat-card">
            <h3>Recent Activity</h3>
            <p>${stats.recent_activity?.last_24h || 0}</p>
            <div class="stat-trend">
                <i class="fas fa-clock"></i>
                <span>Last 24 hours</span>
            </div>
        </div>
    `;
    
    document.getElementById('stats-container').innerHTML = statsHTML;
}

// Load managers with pagination and filters
async function loadManagers() {
    try {
        // Build query parameters
        const params = new URLSearchParams({
            skip: (currentPage - 1) * pageSize,
            limit: pageSize,
            sort_by: currentSort.field,
            sort_order: currentSort.order
        });
        
        if (currentFilters.search) {
            params.append('search', currentFilters.search);
        }
        
        const response = await fetch(`/api/managers?${params}`);
        if (!response.ok) throw new Error('Failed to load managers');
        
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Failed to load managers');
        
        totalManagers = data.pagination?.total || 0;
        updateManagersTable(data.managers || []);
        updatePaginationControls(data.pagination || {});
        
    } catch (error) {
        console.error('Error loading managers:', error);
        document.getElementById('managers-body').innerHTML = `
            <tr>
                <td colspan="8" class="error-row">
                    <div class="status-error">
                        <i class="fas fa-exclamation-triangle"></i>
                        Failed to load managers: ${error.message}
                    </div>
                </td>
            </tr>
        `;
    }
}

// Update managers table
function updateManagersTable(managers) {
    const tbody = document.getElementById('managers-body');
    
    if (!managers || managers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px;">
                    <i class="fas fa-users-slash fa-2x" style="color: #95a5a6; margin-bottom: 15px;"></i>
                    <h3 style="color: #7f8c8d; margin-bottom: 10px;">No Managers Found</h3>
                    <p style="color: #95a5a6;">Try adjusting your filters or add new assessments</p>
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    
    managers.forEach(manager => {
        const percentages = manager.percentages || {};
        const categoryTotals = manager.category_totals || {};
        
        // Determine score classes
        const getScoreClass = (percentage) => {
            if (percentage >= 75) return 'high';
            if (percentage >= 50) return 'medium';
            return 'low';
        };
        
        const trustingClass = getScoreClass(percentages.trusting || 0);
        const taskingClass = getScoreClass(percentages.tasking || 0);
        const tendingClass = getScoreClass(percentages.tending || 0);
        const overallClass = getScoreClass(manager.overall_percentage || 0);
        
        html += `
            <tr>
                <td>
                    <div class="manager-name">
                        <strong>${escapeHtml(manager.manager_name)}</strong>
                        ${manager.raw_manager_name && manager.raw_manager_name !== manager.manager_name ? 
                          `<small>(${escapeHtml(manager.raw_manager_name)})</small>` : ''}
                    </div>
                </td>
                <td>${escapeHtml(manager.reporting_to || 'N/A')}</td>
                <td>
                    <div class="assessment-count">
                        <span class="count-badge">${manager.total_assessments || 0}</span>
                        <small>assessments</small>
                    </div>
                </td>
                <td>
                    <div class="score-cell">
                        <span class="score-value">${categoryTotals.trusting || 0}</span>
                        <div class="score-progress">
                            <div class="score-progress-fill ${trustingClass}" 
                                 style="width: ${percentages.trusting || 0}%"></div>
                        </div>
                        <small>${(percentages.trusting || 0).toFixed(1)}%</small>
                    </div>
                </td>
                <td>
                    <div class="score-cell">
                        <span class="score-value">${categoryTotals.tasking || 0}</span>
                        <div class="score-progress">
                            <div class="score-progress-fill ${taskingClass}" 
                                 style="width: ${percentages.tasking || 0}%"></div>
                        </div>
                        <small>${(percentages.tasking || 0).toFixed(1)}%</small>
                    </div>
                </td>
                <td>
                    <div class="score-cell">
                        <span class="score-value">${categoryTotals.tending || 0}</span>
                        <div class="score-progress">
                            <div class="score-progress-fill ${tendingClass}" 
                                 style="width: ${percentages.tending || 0}%"></div>
                        </div>
                        <small>${(percentages.tending || 0).toFixed(1)}%</small>
                    </div>
                </td>
                <td>
                    <div class="score-cell">
                        <span class="score-value">${manager.overall_percentage ? manager.overall_percentage.toFixed(1) : 0}%</span>
                        <div class="score-progress">
                            <div class="score-progress-fill ${overallClass}" 
                                 style="width: ${manager.overall_percentage || 0}%"></div>
                        </div>
                        <small>Overall</small>
                    </div>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-action btn-view" onclick="viewManagerDetails('${encodeURIComponent(manager.manager_name)}')">
                            <i class="fas fa-chart-pie"></i> View
                        </button>
                        <button class="btn-action btn-report" onclick="generateAIReportForManager('${encodeURIComponent(manager.manager_name)}')">
                            <i class="fas fa-robot"></i> AI Report
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// Update pagination controls
function updatePaginationControls(pagination) {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    const paginationInfo = document.getElementById('pagination-info');
    
    const totalPages = Math.ceil(totalManagers / pageSize);
    
    // Update buttons
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    
    // Update info text
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    
    const start = (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, totalManagers);
    paginationInfo.textContent = `Showing ${start}-${end} of ${totalManagers}`;
}

// Change page
function changePage(delta) {
    const newPage = currentPage + delta;
    const totalPages = Math.ceil(totalManagers / pageSize);
    
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadManagers();
    }
}

// Sort table
function sortTable(field) {
    if (currentSort.field === field) {
        // Toggle order
        currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc';
    } else {
        // New field, default to desc
        currentSort.field = field;
        currentSort.order = 'desc';
    }
    
    loadManagers();
}

// Apply filters
function applyFilters() {
    currentPage = 1; // Reset to first page
    loadManagers();
}

// Clear filters
function clearFilters() {
    document.getElementById('search-input').value = '';
    document.getElementById('assessment-filter').value = 'all';
    document.getElementById('score-filter').value = 'all';
    
    currentFilters = {};
    currentPage = 1;
    
    loadManagers();
}

// Load hierarchy preview
async function loadHierarchyPreview() {
    try {
        const response = await fetch('/api/hierarchy');
        if (!response.ok) throw new Error('Failed to load hierarchy');
        
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Failed to load hierarchy');
        
        updateHierarchyPreview(data);
    } catch (error) {
        console.error('Error loading hierarchy:', error);
        document.getElementById('hierarchy-preview').innerHTML = `
            <div class="status-error">
                <i class="fas fa-exclamation-triangle"></i>
                Failed to load hierarchy
            </div>
        `;
    }
}

// Update hierarchy preview
function updateHierarchyPreview(data) {
    const rootManagers = data.root_managers || [];
    const hierarchy = data.hierarchy || {};
    
    let html = '';
    
    // Show first 5 root managers with their teams
    rootManagers.slice(0, 5).forEach(manager => {
        const managerName = manager.manager_name;
        const team = hierarchy[managerName] || [];
        
        html += `
            <div class="hierarchy-node" onclick="viewManagerDetails('${encodeURIComponent(managerName)}')">
                <div class="node-name">${escapeHtml(managerName)}</div>
                <div class="node-info">
                    <span>${manager.total_assessments || 0} assessments</span>
                    <span>${team.length} direct reports</span>
                </div>
            </div>
        `;
    });
    
    if (rootManagers.length === 0) {
        html = `
            <div style="text-align: center; padding: 20px; color: #7f8c8d;">
                <i class="fas fa-sitemap fa-2x" style="margin-bottom: 10px;"></i>
                <p>No hierarchy data available</p>
            </div>
        `;
    }
    
    document.getElementById('hierarchy-preview').innerHTML = html;
}

// View manager details and show triangle visualization
async function viewManagerDetails(managerName) {
    showLoading(`Loading data for ${decodeURIComponent(managerName)}...`);
    
    try {
        const response = await fetch(`/api/manager/${managerName}?include_assessments=true`);
        if (!response.ok) throw new Error('Failed to load manager details');
        
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Failed to load manager details');
        
        selectedManager = data.manager;
        showTriangleVisualization();
        updateTriangleData();
        
    } catch (error) {
        console.error('Error loading manager details:', error);
        showError(`Failed to load details for ${decodeURIComponent(managerName)}`);
    } finally {
        hideLoading();
    }
}

// Show triangle visualization section
function showTriangleVisualization() {
    // Hide other sections
    document.getElementById('ai-report-section').style.display = 'none';
    
    // Show triangle section
    document.getElementById('triangle-section').style.display = 'block';
    
    // Scroll to section
    document.getElementById('triangle-section').scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
    });
}

// Hide triangle visualization
function hideTriangleSection() {
    document.getElementById('triangle-section').style.display = 'none';
}

// Update triangle visualization with data
function updateTriangleData() {
    if (!selectedManager) return;
    
    const manager = selectedManager;
    const percentages = manager.percentages || {};
    const visualization = manager.visualization || {};
    const categoryTotals = manager.category_totals || {};
    
    // Update manager info
    document.getElementById('selected-manager-name').textContent = manager.manager_name;
    document.getElementById('selected-manager-reporting').textContent = 
        `Reports to: ${manager.reporting_to || 'N/A'}`;
    document.getElementById('selected-manager-assessments').textContent = 
        `Assessments: ${manager.total_assessments || 0}`;
    
    // Update score breakdown
    const maxPerCategory = visualization.max_scores?.per_category || 36 * (manager.total_assessments || 1);
    
    // Trusting
    const trustingPercentage = percentages.trusting || 0;
    document.getElementById('trusting-score').textContent = 
        `${categoryTotals.trusting || 0}/${maxPerCategory}`;
    document.getElementById('trusting-percentage').textContent = 
        `${trustingPercentage.toFixed(1)}%`;
    document.getElementById('trusting-fill').style.width = `${trustingPercentage}%`;
    
    // Tasking
    const taskingPercentage = percentages.tasking || 0;
    document.getElementById('tasking-score').textContent = 
        `${categoryTotals.tasking || 0}/${maxPerCategory}`;
    document.getElementById('tasking-percentage').textContent = 
        `${taskingPercentage.toFixed(1)}%`;
    document.getElementById('tasking-fill').style.width = `${taskingPercentage}%`;
    
    // Tending
    const tendingPercentage = percentages.tending || 0;
    document.getElementById('tending-score').textContent = 
        `${categoryTotals.tending || 0}/${maxPerCategory}`;
    document.getElementById('tending-percentage').textContent = 
        `${tendingPercentage.toFixed(1)}%`;
    document.getElementById('tending-fill').style.width = `${tendingPercentage}%`;
    
    // Create or update triangle chart
    createTriangleChart(trustingPercentage, taskingPercentage, tendingPercentage);
}

// Create triangle chart (radar chart)
function createTriangleChart(trusting, tasking, tending) {
    const ctx = document.getElementById('triangle-chart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (triangleChart) {
        triangleChart.destroy();
    }
    
    triangleChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Trusting', 'Tasking', 'Tending'],
            datasets: [{
                label: 'Scores (%)',
                data: [trusting, tasking, tending],
                backgroundColor: 'rgba(52, 152, 219, 0.2)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(52, 152, 219, 1)',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    angleLines: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    ticks: {
                        stepSize: 25,
                        backdropColor: 'transparent'
                    },
                    pointLabels: {
                        font: {
                            size: 14,
                            weight: 'bold'
                        },
                        color: '#2c3e50'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw}%`;
                        }
                    }
                }
            }
        }
    });
}

// Generate AI report for manager
async function generateAIReportForManager(managerName) {
    showLoading(`Generating AI analysis for ${decodeURIComponent(managerName)}...`);
    
    try {
        // First, trigger report generation
        const generateResponse = await fetch(`/api/manager/${managerName}/generate-report`, {
            method: 'POST'
        });
        
        if (!generateResponse.ok) throw new Error('Failed to start AI report generation');
        
        const generateData = await generateResponse.json();
        
        if (!generateData.success) {
            throw new Error(generateData.error || 'Failed to generate AI report');
        }
        
        // Wait a moment, then fetch the report
        setTimeout(async () => {
            try {
                const reportResponse = await fetch(`/api/manager/${managerName}/report`);
                if (!reportResponse.ok) throw new Error('Failed to fetch AI report');
                
                const reportData = await reportResponse.json();
                
                if (!reportData.success) {
                    throw new Error(reportData.error || 'Failed to fetch AI report');
                }
                
                // Show the report
                showAIReport(reportData.report);
                
            } catch (error) {
                console.error('Error fetching AI report:', error);
                showError('Failed to generate AI report. Please try again.');
            } finally {
                hideLoading();
            }
        }, 3000); // Wait 3 seconds for generation
        
    } catch (error) {
        console.error('Error generating AI report:', error);
        showError(error.message || 'Failed to generate AI report');
        hideLoading();
    }
}

// Show AI report
function showAIReport(report) {
    // Hide triangle section
    document.getElementById('triangle-section').style.display = 'none';
    
    // Show AI report section
    document.getElementById('ai-report-section').style.display = 'block';
    
    // Parse and display AI analysis
    const aiContent = report.ai_analysis || 'No AI analysis available.';
    
    // Simple markdown-like formatting
    let formattedContent = aiContent
        .replace(/## (.*?)\n/g, '<h4>$1</h4>')
        .replace(/# (.*?)\n/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
    
    // Wrap in paragraphs
    formattedContent = formattedContent
        .split('</p><p>')
        .map(para => `<p>${para}</p>`)
        .join('');
    
    document.getElementById('ai-report-content').innerHTML = `
        <div class="report-section">
            <h3>AI Leadership Analysis</h3>
            <div class="report-meta">
                <p><strong>Manager:</strong> ${report.manager_name || 'N/A'}</p>
                <p><strong>Generated:</strong> ${new Date(report.analysis_date || report.created_at).toLocaleString()}</p>
            </div>
            <div class="report-content">
                ${formattedContent}
            </div>
        </div>
    `;
    
    // Scroll to report section
    document.getElementById('ai-report-section').scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
    });
}

// Hide AI report
function hideAIReport() {
    document.getElementById('ai-report-section').style.display = 'none';
}

// Download manager report (PDF)
async function downloadManagerReport() {
    if (!selectedManager) {
        showError('No manager selected');
        return;
    }
    
    showLoading('Generating PDF report...');
    
    try {
        const managerName = encodeURIComponent(selectedManager.manager_name);
        window.open(`/api/manager/${managerName}/report/pdf`, '_blank');
        
    } catch (error) {
        console.error('Error downloading report:', error);
        showError('Failed to download report');
    } finally {
        hideLoading();
    }
}

// Download PDF (for AI report)
async function downloadPDF() {
    if (!selectedManager) {
        showError('No manager selected');
        return;
    }
    
    showLoading('Downloading PDF...');
    // Implementation depends on your backend PDF generation endpoint
    hideLoading();
}

// Email report
async function emailReport() {
    if (!selectedManager) {
        showError('No manager selected');
        return;
    }
    
    showEmailModal();
}

// Show email modal
function showEmailModal() {
    document.getElementById('email-modal').style.display = 'flex';
    document.getElementById('email-recipients').value = '';
    document.getElementById('email-message').value = '';
    document.getElementById('email-status').innerHTML = '';
}

// Close email modal
function closeEmailModal() {
    document.getElementById('email-modal').style.display = 'none';
}

// Send email
async function sendEmail() {
    const recipients = document.getElementById('email-recipients').value.trim();
    const message = document.getElementById('email-message').value.trim();
    
    if (!recipients) {
        document.getElementById('email-status').innerHTML = `
            <div class="status-error">Please enter email addresses</div>
        `;
        return;
    }
    
    const emailList = recipients.split(',').map(email => email.trim()).filter(email => email);
    
    showLoading('Sending email...');
    
    try {
        const managerName = encodeURIComponent(selectedManager.manager_name);
        const response = await fetch(`/api/report/${managerName}/email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                emails: emailList,
                message: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('email-status').innerHTML = `
                <div class="status-success">
                    <i class="fas fa-check-circle"></i> Email sent successfully!
                </div>
            `;
            
            // Close modal after 2 seconds
            setTimeout(() => {
                closeEmailModal();
            }, 2000);
        } else {
            throw new Error(data.error || 'Failed to send email');
        }
        
    } catch (error) {
        console.error('Error sending email:', error);
        document.getElementById('email-status').innerHTML = `
            <div class="status-error">
                <i class="fas fa-exclamation-triangle"></i> Failed to send email: ${error.message}
            </div>
        `;
    } finally {
        hideLoading();
    }
}

// Show hierarchy modal
async function showHierarchyModal() {
    showLoading('Loading full hierarchy...');
    
    try {
        const response = await fetch('/api/hierarchy/tree');
        if (!response.ok) throw new Error('Failed to load hierarchy');
        
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Failed to load hierarchy');
        
        displayFullHierarchy(data);
        document.getElementById('hierarchy-modal').style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading hierarchy:', error);
        showError('Failed to load hierarchy');
    } finally {
        hideLoading();
    }
}

// Display full hierarchy
function displayFullHierarchy(data) {
    const container = document.getElementById('hierarchy-container');
    
    function renderNode(node, level = 0) {
        const indent = level * 20;
        
        return `
            <div class="hierarchy-tree-node" style="margin-left: ${indent}px;">
                <div class="tree-node-content" onclick="viewManagerDetails('${encodeURIComponent(node.name)}')">
                    <div class="tree-node-header">
                        <span class="tree-node-name">${escapeHtml(node.name)}</span>
                        <span class="tree-node-badge">${node.total_assessments} assessments</span>
                    </div>
                    <div class="tree-node-scores">
                        <span class="score-badge trusting">T: ${node.percentages.trusting}%</span>
                        <span class="score-badge tasking">K: ${node.percentages.tasking}%</span>
                        <span class="score-badge tending">D: ${node.percentages.tending}%</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    function renderTree(nodes, level = 0) {
        let html = '';
        
        nodes.forEach(node => {
            html += renderNode(node, level);
            // Find children
            const children = data.tree[node.name] || [];
            if (children.length > 0) {
                html += renderTree(children, level + 1);
            }
        });
        
        return html;
    }
    
    const roots = data.roots || [];
    container.innerHTML = renderTree(roots);
}

// Close hierarchy modal
function closeHierarchyModal() {
    document.getElementById('hierarchy-modal').style.display = 'none';
}

// Show migration modal
function showMigrationModal() {
    document.getElementById('migration-modal').style.display = 'flex';
    document.getElementById('migration-status').innerHTML = '';
}

// Close migration modal
function closeMigrationModal() {
    document.getElementById('migration-modal').style.display = 'none';
}

// Run migration
async function runMigration() {
    showLoading('Migrating data...');
    
    try {
        const response = await fetch('/api/migrate', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('migration-status').innerHTML = `
                <div class="status-success">
                    <i class="fas fa-check-circle"></i> Migration successful!
                    <br><br>
                    <strong>Details:</strong><br>
                    • Created: ${data.data.created} new entries<br>
                    • Updated: ${data.data.updated} existing entries<br>
                    • Total managers: ${data.data.total}
                </div>
            `;
            
            // Refresh data after migration
            setTimeout(() => {
                refreshAllData();
            }, 2000);
        } else {
            throw new Error(data.error || 'Migration failed');
        }
        
    } catch (error) {
        console.error('Error migrating data:', error);
        document.getElementById('migration-status').innerHTML = `
            <div class="status-error">
                <i class="fas fa-exclamation-triangle"></i> Migration failed: ${error.message}
            </div>
        `;
    } finally {
        hideLoading();
    }
}

// Export data
async function exportData() {
    showLoading('Preparing export...');
    
    try {
        window.open('/api/export/managers/csv', '_blank');
    } catch (error) {
        console.error('Error exporting data:', error);
        showError('Failed to export data');
    } finally {
        hideLoading();
    }
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(message = 'Loading...') {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function showSuccess(message) {
    // Create temporary success message
    const successDiv = document.createElement('div');
    successDiv.className = 'status-success';
    successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    successDiv.style.position = 'fixed';
    successDiv.style.top = '20px';
    successDiv.style.right = '20px';
    successDiv.style.zIndex = '1000';
    successDiv.style.padding = '15px';
    successDiv.style.borderRadius = '8px';
    successDiv.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
    
    document.body.appendChild(successDiv);
    
    // Remove after 3 seconds
    setTimeout(() => {
        document.body.removeChild(successDiv);
    }, 3000);
}

function showError(message) {
    // Create temporary error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'status-error';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    errorDiv.style.position = 'fixed';
    errorDiv.style.top = '20px';
    errorDiv.style.right = '20px';
    errorDiv.style.zIndex = '1000';
    errorDiv.style.padding = '15px';
    errorDiv.style.borderRadius = '8px';
    errorDiv.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
    
    document.body.appendChild(errorDiv);
    
    // Remove after 5 seconds
    setTimeout(() => {
        document.body.removeChild(errorDiv);
    }, 5000);
}

// Add some CSS for the hierarchy tree in modal
const style = document.createElement('style');
style.textContent = `
    .hierarchy-tree-node {
        margin: 10px 0;
        padding: 10px;
        border-left: 3px solid #3498db;
        background: #f8f9fa;
        border-radius: 0 8px 8px 0;
        transition: all 0.2s ease;
    }
    
    .hierarchy-tree-node:hover {
        background: #e8f4fc;
        transform: translateX(5px);
    }
    
    .tree-node-content {
        cursor: pointer;
    }
    
    .tree-node-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    
    .tree-node-name {
        font-weight: 600;
        color: #2c3e50;
        font-size: 16px;
    }
    
    .tree-node-badge {
        background: #3498db;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .tree-node-scores {
        display: flex;
        gap: 10px;
    }
    
    .score-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .score-badge.trusting {
        background: #3498db;
        color: white;
    }
    
    .score-badge.tasking {
        background: #2ecc71;
        color: white;
    }
    
    .score-badge.tending {
        background: #e74c3c;
        color: white;
    }
    
    .count-badge {
        display: inline-block;
        background: #3498db;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 5px;
    }
    
    .error-row {
        text-align: center;
        padding: 40px !important;
    }
`;
document.head.appendChild(style);