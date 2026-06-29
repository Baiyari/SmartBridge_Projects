import os

file_path = "index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add CSS rules
css_rules = """
        /* Data Status Card */
        .data-status-card {
            background: var(--md-sys-color-surface);
            border-radius: 16px;
            padding: 24px;
            box-shadow: var(--md-elevation-2);
            margin-bottom: 24px;
            border-left: 4px solid var(--md-sys-color-primary);
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 24px;
        }

        .data-status-col {
            display: flex;
            align-items: center;
            gap: 16px;
            border-right: 1px solid #f0f4ff;
            padding-right: 24px;
            position: relative;
        }
        
        .data-status-col:last-child {
            border-right: none;
            padding-right: 0;
        }

        .data-icon-circle {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(26, 115, 232, 0.1);
            color: var(--md-sys-color-primary);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }

        .data-col-content {
            display: flex;
            flex-direction: column;
            gap: 4px;
            width: 100%;
        }

        .data-label {
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .data-value {
            font-size: 16px;
            font-weight: 700;
            color: var(--md-sys-color-on-surface);
        }

        .data-subtext {
            font-size: 12px;
            color: #64748b;
        }

        .status-chip-corner {
            position: absolute;
            top: 0;
            right: 24px;
            padding: 4px 8px;
            border-radius: 100px;
            font-size: 10px;
            font-weight: 600;
            background: rgba(0, 200, 83, 0.1);
            color: var(--risk-low);
        }

        .data-status-col:last-child .status-chip-corner {
            right: 0;
        }

        .run-analysis-btn {
            background: var(--md-sys-color-primary);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--md-transition);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            margin-top: 4px;
        }

        .run-analysis-btn:hover {
            background: #0d47a1;
        }

        /* Toast notification */
        .toast-notification {
            position: fixed;
            bottom: 32px;
            right: 32px;
            padding: 16px 24px;
            border-radius: 8px;
            background: white;
            box-shadow: var(--md-elevation-hover);
            display: flex;
            align-items: center;
            gap: 12px;
            transform: translateY(150%);
            transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 9999;
            font-weight: 500;
            color: var(--md-sys-color-on-surface);
            font-size: 14px;
        }
        
        .toast-notification.show {
            transform: translateY(0);
        }

        .toast-notification.success { border-left: 4px solid var(--risk-low); }
        .toast-notification.error { border-left: 4px solid var(--risk-critical); }
"""
content = content.replace("</style>", css_rules + "\n    </style>")

# 2. Add Data Source Status Card
data_card_html = """
            <h2 class="page-title" style="margin-bottom: 8px;">Overview</h2>
            
            <div class="data-status-card" id="data-status-card">
                <div class="data-status-col">
                    <div class="data-icon-circle"><i class="fa-solid fa-database"></i></div>
                    <div class="data-col-content">
                        <div class="data-label">Data Source</div>
                        <div class="data-value">IBM HR Analytics</div>
                        <div class="data-subtext">CSV · 1,470 Records</div>
                    </div>
                    <div class="status-chip-corner">Connected</div>
                </div>
                <div class="data-status-col">
                    <div class="data-icon-circle"><i class="fa-regular fa-clock"></i></div>
                    <div class="data-col-content">
                        <div class="data-label">Last Refreshed</div>
                        <div class="data-value" id="last-refreshed-time">Loading...</div>
                        <div class="data-subtext">Auto-refreshes on analysis run</div>
                    </div>
                    <div class="status-chip-corner">Live</div>
                </div>
                <div class="data-status-col">
                    <div class="data-icon-circle"><i class="fa-solid fa-chart-line"></i></div>
                    <div class="data-col-content">
                        <div class="data-label">Pipeline Status</div>
                        <div class="data-value">All Systems Active</div>
                        <div class="data-subtext">7 behavioral signals active</div>
                    </div>
                    <div class="status-chip-corner">Healthy</div>
                </div>
                <div class="data-status-col">
                    <div class="data-col-content" style="gap: 0;">
                        <div class="data-label" style="margin-bottom: 4px;">Re-run Analysis</div>
                        <button class="run-analysis-btn" id="run-analysis-btn" onclick="runAnalysis()">
                            <i class="fa-solid fa-play"></i> Run Analysis
                        </button>
                        <div class="data-subtext" style="text-align: center; margin-top: 4px;">Triggers full AI pipeline</div>
                    </div>
                </div>
            </div>
"""
content = content.replace('<h2 class="page-title">Overview</h2>', data_card_html)

# 3. Add Attrition Trend Chart
trend_chart_html = """
                <!-- Chart 1: Department Attrition Bar Chart (Full Width) -->
                <div class="chart-card full-width">
                    <div class="chart-header">
                        <div class="chart-title">Attrition Risk by Department</div>
                    </div>
                    <div class="chart-container">
                        <canvas id="barChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- New Addition: Attrition Trend Chart -->
            <div class="chart-card full-width" style="margin-bottom: 24px; height: 320px;">
                <div class="chart-header" style="margin-bottom: 8px;">
                    <div class="chart-title" style="font-size: 15px;">Attrition Risk Trend by Years at Company</div>
                    <div style="font-size: 13px; color: #64748b; margin-top: 4px;">How risk evolves across employee tenure</div>
                </div>
                <div class="chart-container">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
"""
# Replace the end of charts-grid
target_end = """                <!-- Chart 1: Department Attrition Bar Chart (Full Width) -->
                <div class="chart-card full-width">
                    <div class="chart-header">
                        <div class="chart-title">Attrition Risk by Department</div>
                    </div>
                    <div class="chart-container">
                        <canvas id="barChart"></canvas>
                    </div>
                </div>
            </div>"""
content = content.replace(target_end, trend_chart_html)

# 4. Add Toast to Body
toast_html = """
    <div class="toast-notification" id="system-toast">
        <i class="fa-solid fa-circle-check toast-icon" style="font-size: 18px;"></i>
        <div class="toast-message" id="toast-message">Notification</div>
    </div>
"""
content = content.replace("</body>", toast_html + "\n</body>")

# 5. Add JS functions
js_additions = """
        let trendChartInstance = null;

        // Initialize current time for Last Refreshed
        function updateRefreshTime() {
            const now = new Date();
            const options = { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' };
            document.getElementById('last-refreshed-time').innerText = now.toLocaleDateString('en-GB', options).replace(',', '');
        }
        
        // Setup initial time
        document.addEventListener('DOMContentLoaded', () => {
            updateRefreshTime();
        });

        function showToast(message, type) {
            const toast = document.getElementById('system-toast');
            const msgEl = document.getElementById('toast-message');
            const iconEl = toast.querySelector('.toast-icon');
            
            toast.className = 'toast-notification ' + type;
            msgEl.innerText = message;
            
            if (type === 'success') {
                iconEl.className = 'fa-solid fa-circle-check toast-icon';
                iconEl.style.color = 'var(--risk-low)';
            } else {
                iconEl.className = 'fa-solid fa-circle-xmark toast-icon';
                iconEl.style.color = 'var(--risk-critical)';
            }
            
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        async function runAnalysis() {
            const btn = document.getElementById('run-analysis-btn');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running...';
            btn.disabled = true;
            
            try {
                const res = await fetch(API_BASE + '/analyze?send_alerts=false', { method: 'POST' });
                if (!res.ok) throw new Error('API Error');
                const data = await res.json();
                
                showToast('Analysis complete · Data refreshed', 'success');
                updateRefreshTime();
                
                // Refresh data
                await loadDashboard();
                await loadEmployees();
                await loadAlerts();
            } catch (err) {
                console.error(err);
                showToast('Pipeline error · Check backend', 'error');
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        }

        // Add trend chart loading inside loadDashboard
        async function loadTrendChart() {
            // We need 1500 limit to get all employees for grouping
            const data = await fetchAPI('/employees?limit=1500');
            if (!data || !data.employees) return;
            
            const bands = [
                { label: "0-1 yrs", min: 0, max: 1, emps: [] },
                { label: "2-3 yrs", min: 2, max: 3, emps: [] },
                { label: "4-5 yrs", min: 4, max: 5, emps: [] },
                { label: "6-8 yrs", min: 6, max: 8, emps: [] },
                { label: "9-12 yrs", min: 9, max: 12, emps: [] },
                { label: "13+ yrs", min: 13, max: 999, emps: [] }
            ];
            
            data.employees.forEach(emp => {
                const tenure = emp.years_at_company || emp.YearsAtCompany || 0; // check mapping
                for (let b of bands) {
                    if (tenure >= b.min && tenure <= b.max) {
                        b.emps.push(emp);
                        break;
                    }
                }
            });
            
            const labels = [];
            const avgScores = [];
            const highPct = [];
            const counts = [];
            
            bands.forEach(b => {
                labels.push(b.label);
                counts.push(b.emps.length);
                if (b.emps.length === 0) {
                    avgScores.push(0);
                    highPct.push(0);
                    return;
                }
                
                let totalScore = 0;
                let highCritCount = 0;
                
                b.emps.forEach(e => {
                    totalScore += e.composite_score || 0;
                    if (e.risk_band === 'HIGH' || e.risk_band === 'CRITICAL') {
                        highCritCount++;
                    }
                });
                
                avgScores.push(Math.round(totalScore / b.emps.length));
                highPct.push(Math.round((highCritCount / b.emps.length) * 100));
            });
            
            const ctx = document.getElementById('trendChart').getContext('2d');
            
            if (trendChartInstance) trendChartInstance.destroy();
            
            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, 'rgba(26,115,232,0.25)');
            gradient.addColorStop(1, 'rgba(26,115,232,0)');
            
            trendChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Avg Risk Score',
                            data: avgScores,
                            borderColor: '#1a73e8',
                            backgroundColor: gradient,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#1a73e8',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 6,
                            pointHoverRadius: 8,
                            yAxisID: 'y'
                        },
                        {
                            label: '% High/Critical',
                            data: highPct,
                            borderColor: '#d50000',
                            backgroundColor: 'transparent',
                            borderDash: [5, 5],
                            tension: 0.4,
                            pointBackgroundColor: '#d50000',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 6,
                            pointHoverRadius: 8,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            align: 'end',
                            labels: {
                                usePointStyle: true,
                                boxWidth: 6
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.9)',
                            titleFont: { size: 13, family: 'Inter' },
                            bodyFont: { size: 13, family: 'Inter' },
                            padding: 12,
                            callbacks: {
                                title: function(context) {
                                    return 'Tenure: ' + context[0].label;
                                },
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += context.parsed.y + (context.datasetIndex === 1 ? '%' : '');
                                    }
                                    return label;
                                },
                                afterBody: function(context) {
                                    return 'Employees in group: ' + counts[context[0].dataIndex];
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                color: '#f0f4ff',
                                drawBorder: false
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Avg Risk Score',
                                color: '#64748b',
                                font: { size: 12, family: 'Inter' }
                            },
                            grid: {
                                color: '#f0f4ff',
                                drawBorder: false
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: '% High/Critical',
                                color: '#64748b',
                                font: { size: 12, family: 'Inter' }
                            },
                            grid: {
                                drawOnChartArea: false,
                                drawBorder: false
                            }
                        }
                    },
                    animation: {
                        duration: 2000,
                        easing: 'easeOutQuart'
                    }
                }
            });
        }
"""
content = content.replace("// ---------------- DASHBOARD LOAD ----------------", js_additions + "\n        // ---------------- DASHBOARD LOAD ----------------")

# Let's insert loadTrendChart() inside loadDashboard()
# Find the end of loadDashboard
target_load_dashboard = """                const tr = document.createElement('tr');
                tr.onclick = () => openDetailPanel(fullData.employee_id ? fullData : emp);"""
load_dashboard_addition = """
            await loadTrendChart();
            
            data.top_at_risk.forEach((emp, i) => {
                const fullData = detailedEmployees[i] || {};
                const activeFlags = fullData.active_flags || {};
                
                let primarySignal = "Multiple Signals";
                let topFlags = Object.entries(activeFlags).filter(f => f[1]).map(f => flagHRNames[f[0]] || f[0]);
                if (topFlags.length === 1) primarySignal = topFlags[0];
                else if (topFlags.length > 1) primarySignal = topFlags[0]; // Just take first as primary
                else primarySignal = "Baseline Risk";

                const tr = document.createElement('tr');
                tr.onclick = () => openDetailPanel(fullData.employee_id ? fullData : emp);"""
content = content.replace("""            data.top_at_risk.forEach((emp, i) => {
                const fullData = detailedEmployees[i] || {};
                const activeFlags = fullData.active_flags || {};
                
                let primarySignal = "Multiple Signals";
                let topFlags = Object.entries(activeFlags).filter(f => f[1]).map(f => flagHRNames[f[0]] || f[0]);
                if (topFlags.length === 1) primarySignal = topFlags[0];
                else if (topFlags.length > 1) primarySignal = topFlags[0]; // Just take first as primary
                else primarySignal = "Baseline Risk";

                const tr = document.createElement('tr');
                tr.onclick = () => openDetailPanel(fullData.employee_id ? fullData : emp);""", load_dashboard_addition)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
