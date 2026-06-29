document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    lucide.createIcons();

    // =========================================================
    // AUTH SYSTEM
    // =========================================================

    // --- Toast utility ---
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => {
            requestAnimationFrame(() => toast.classList.add('toast-visible'));
        });
        setTimeout(() => {
            toast.classList.remove('toast-visible');
            setTimeout(() => toast.remove(), 400);
        }, 3200);
    }

    // --- Nav state ---
    const navLoggedOut = document.getElementById('nav-auth-loggedout');
    const navLoggedIn  = document.getElementById('nav-auth-loggedin');
    const navUserInitial = document.getElementById('nav-user-initial');
    const navUserName    = document.getElementById('nav-user-name');

    function setLoggedInNav(user) {
        navLoggedOut.style.display = 'none';
        navLoggedIn.style.display  = 'flex';
        navUserInitial.textContent = (user.name || user.email || '?')[0].toUpperCase();
        navUserName.textContent    = user.name || user.email;
    }

    function setLoggedOutNav() {
        navLoggedOut.style.display = 'flex';
        navLoggedIn.style.display  = 'none';
    }

    // --- Restore session on load ---
    (function restoreSession() {
        const token = localStorage.getItem('regintel_token');
        if (!token) return;
        fetch('/api/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.user) {
                setLoggedInNav(data.user);
            } else {
                localStorage.removeItem('regintel_token');
                localStorage.removeItem('regintel_user');
            }
        })
        .catch(() => {});
    })();

    // --- Modal elements ---
    const authModal       = document.getElementById('auth-modal');
    const authModalClose  = document.getElementById('auth-modal-close');
    const authTabLogin    = document.getElementById('auth-tab-login');
    const authTabSignup   = document.getElementById('auth-tab-signup');
    const authFormLogin   = document.getElementById('auth-form-login');
    const authFormSignup  = document.getElementById('auth-form-signup');

    function openModal(tab) {
        authModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        lucide.createIcons({ root: authModal });
        switchAuthTab(tab || 'login');
    }

    function closeModal() {
        authModal.style.display = 'none';
        document.body.style.overflow = '';
        document.getElementById('login-error').textContent  = '';
        document.getElementById('signup-error').textContent = '';
    }

    function switchAuthTab(tab) {
        if (tab === 'login') {
            authTabLogin.classList.add('active');
            authTabSignup.classList.remove('active');
            authFormLogin.style.display  = 'block';
            authFormSignup.style.display = 'none';
        } else {
            authTabSignup.classList.add('active');
            authTabLogin.classList.remove('active');
            authFormSignup.style.display = 'block';
            authFormLogin.style.display  = 'none';
        }
    }

    // Open modal from nav
    document.getElementById('nav-login-btn').addEventListener('click',  () => openModal('login'));
    document.getElementById('nav-signup-btn').addEventListener('click', () => openModal('signup'));

    // Close modal
    authModalClose.addEventListener('click', closeModal);
    authModal.addEventListener('click', (e) => { if (e.target === authModal) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && authModal.style.display !== 'none') closeModal(); });

    // Tab switching inside modal
    authTabLogin.addEventListener('click',  () => switchAuthTab('login'));
    authTabSignup.addEventListener('click', () => switchAuthTab('signup'));

    // --- Login submit ---
    document.getElementById('login-submit-btn').addEventListener('click', async () => {
        const email    = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const errEl    = document.getElementById('login-error');
        errEl.textContent = '';

        if (!email || !password) { errEl.textContent = 'Please fill in all fields.'; return; }

        const btn = document.getElementById('login-submit-btn');
        btn.textContent = 'Logging in…';
        btn.disabled = true;

        try {
            const res  = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok) { errEl.textContent = data.error || 'Login failed.'; return; }

            localStorage.setItem('regintel_token', data.token);
            localStorage.setItem('regintel_user',  JSON.stringify(data.user));
            setLoggedInNav(data.user);
            closeModal();
            showToast(`Welcome back, ${data.user.name}!`, 'success');
        } catch (err) {
            errEl.textContent = 'Network error. Please try again.';
        } finally {
            btn.textContent = 'Log In';
            btn.disabled = false;
        }
    });

    // Allow Enter key on login fields
    ['login-email', 'login-password'].forEach(id => {
        document.getElementById(id).addEventListener('keydown', (e) => {
            if (e.key === 'Enter') document.getElementById('login-submit-btn').click();
        });
    });

    // --- Signup submit ---
    document.getElementById('signup-submit-btn').addEventListener('click', async () => {
        const name     = document.getElementById('signup-name').value.trim();
        const email    = document.getElementById('signup-email').value.trim();
        const password = document.getElementById('signup-password').value;
        const errEl    = document.getElementById('signup-error');
        errEl.textContent = '';

        if (!name || !email || !password) { errEl.textContent = 'Please fill in all fields.'; return; }
        if (password.length < 6)          { errEl.textContent = 'Password must be at least 6 characters.'; return; }

        const btn = document.getElementById('signup-submit-btn');
        btn.textContent = 'Creating account…';
        btn.disabled = true;

        try {
            const res  = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            const data = await res.json();
            if (!res.ok) { errEl.textContent = data.error || 'Signup failed.'; return; }

            localStorage.setItem('regintel_token', data.token);
            localStorage.setItem('regintel_user',  JSON.stringify(data.user));
            setLoggedInNav(data.user);
            closeModal();
            showToast('Account created! Welcome to RegIntel.', 'success');
        } catch (err) {
            errEl.textContent = 'Network error. Please try again.';
        } finally {
            btn.textContent = 'Create Account';
            btn.disabled = false;
        }
    });

    // Allow Enter key on signup fields
    ['signup-name', 'signup-email', 'signup-password'].forEach(id => {
        document.getElementById(id).addEventListener('keydown', (e) => {
            if (e.key === 'Enter') document.getElementById('signup-submit-btn').click();
        });
    });

    // --- Logout ---
    document.getElementById('nav-logout-btn').addEventListener('click', () => {
        localStorage.removeItem('regintel_token');
        localStorage.removeItem('regintel_user');
        setLoggedOutNav();
        showToast('You have been logged out.', 'info');
    });

    // =========================================================
    // END AUTH SYSTEM
    // =========================================================


    // Chart References
    let severityChart = null;
    let priorityChart = null;
    let historyTimelineChart = null;

    // Interactive filtering state for the results view
    let currentGaps = [];
    let activeRiskFilter = null; // null = no filter, else one of Critical/High/Medium/Low

    // History Data References
    let auditHistoryData = [];
    let currentSortField = 'timestamp';
    let currentSortAsc = false;

    // 1. Navbar Scroll Effect
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // 2. Scroll Reveal Animations (Intersection Observer)
    const revealElements = document.querySelectorAll('.reveal');
    const revealOptions = {
        threshold: 0.15,
        rootMargin: "0px 0px -50px 0px"
    };

    const revealOnScroll = new IntersectionObserver(function(entries, observer) {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('active');
            observer.unobserve(entry.target);
        });
    }, revealOptions);

    revealElements.forEach(el => revealOnScroll.observe(el));

    // 3. Theme Toggle Setup
    const themeToggle = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    function applyTheme(theme) {
        const isLight = theme === 'light';
        if (isLight) {
            document.body.classList.add('light-theme');
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        } else {
            document.body.classList.remove('light-theme');
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        }
        updateChartsTheme(isLight);
    }

    // Load initial theme preference
    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme);

    themeToggle.addEventListener('click', () => {
        const currentlyLight = document.body.classList.contains('light-theme');
        const nextTheme = currentlyLight ? 'dark' : 'light';
        applyTheme(nextTheme);
        localStorage.setItem('theme', nextTheme);
    });

    // Utility to get current theme-specific colors for charts
    function getThemeColors() {
        const isLight = document.body.classList.contains('light-theme');
        return {
            text: isLight ? '#111827' : '#F9F9FA',
            grid: isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.05)',
            cardBg: isLight ? '#FFFFFF' : '#1A1F2D'
        };
    }

    function updateChartsTheme(isLight) {
        const colors = getThemeColors();
        const updateChart = (chart) => {
            if (!chart) return;
            // Update common legend & ticks colors
            if (chart.options.plugins && chart.options.plugins.legend) {
                chart.options.plugins.legend.labels.color = colors.text;
            }
            if (chart.options.scales) {
                for (let key in chart.options.scales) {
                    const scale = chart.options.scales[key];
                    if (scale.ticks) scale.ticks.color = colors.text;
                    if (scale.grid) scale.grid.color = colors.grid;
                }
            }
            chart.update();
        };
        updateChart(severityChart);
        updateChart(priorityChart);
        updateChart(historyTimelineChart);
    }

    // 4. Tab Navigation System
    const tabAuditBtn = document.getElementById('tab-audit-btn');
    const tabHistoryBtn = document.getElementById('tab-history-btn');
    const auditInterface = document.getElementById('audit-interface');
    const historyContainer = document.getElementById('history-container');

    tabAuditBtn.addEventListener('click', () => {
        tabAuditBtn.classList.add('active');
        tabHistoryBtn.classList.remove('active');
        historyContainer.style.display = 'none';
        auditInterface.style.display = 'block';
    });

    tabHistoryBtn.addEventListener('click', () => {
        tabHistoryBtn.classList.add('active');
        tabAuditBtn.classList.remove('active');
        auditInterface.style.display = 'none';
        historyContainer.style.display = 'flex';
        fetchAuditHistory();
    });

    // 5. Interactive Product Demo Elements
    const uploadZone = document.getElementById('upload-zone');
    const processingZone = document.getElementById('processing-zone');
    const resultsZone = document.getElementById('results-zone');
    const errorZone = document.getElementById('error-zone');
    const browseBtn = document.getElementById('browse-btn');
    const fileInput = document.getElementById('file-input');
    const demoFilename = document.getElementById('demo-filename');
    const resetBtn = document.getElementById('reset-demo-btn');
    const errorResetBtn = document.getElementById('error-reset-btn');
    const errorMessage = document.getElementById('error-message');

    // Steps
    const steps = [
        document.getElementById('step-1'),
        document.getElementById('step-2'),
        document.getElementById('step-3'),
        document.getElementById('step-4')
    ];

    let progressTimer = null;

    // Drag and Drop Effects
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            startAuditSequence(e.dataTransfer.files[0]);
        }
    });

    // Button Click
    browseBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            startAuditSequence(e.target.files[0]);
        }
    });

    // Reset Demo
    resetBtn.addEventListener('click', () => {
        resultsZone.classList.remove('active');
        setTimeout(() => {
            resetDemoState();
            uploadZone.classList.add('active');
        }, 300); // Wait for fade out
    });

    errorResetBtn.addEventListener('click', () => {
        errorZone.classList.remove('active');
        setTimeout(() => {
            resetDemoState();
            uploadZone.classList.add('active');
        }, 300);
    });

    function resetDemoState() {
        // Reset steps UI
        steps.forEach((step, index) => {
            step.classList.remove('complete');
            if(index !== 0) {
                step.classList.add('pending');
            } else {
                step.classList.remove('pending');
            }
        });
        
        // Clear dynamic content
        document.getElementById('clause-tags').innerHTML = '';
        document.getElementById('policy-chips').innerHTML = '';
        document.getElementById('risk-fill').style.width = '0%';
        fileInput.value = ''; // Reset input
        errorMessage.textContent = '';
        if (progressTimer) {
            clearTimeout(progressTimer);
            progressTimer = null;
        }
    }

    function startAuditSequence(file) {
        resetDemoState();
        demoFilename.textContent = file.name;
        
        // Hide upload, show processing
        uploadZone.classList.remove('active');
        setTimeout(() => {
            processingZone.classList.add('active');
            runRealAudit(file);
        }, 300);
    }

    function runRealAudit(file) {
        // 1. Start simulating step transitions (active/spinning states only)
        const transitionStep = (index) => {
            if (index < steps.length) {
                progressTimer = setTimeout(() => {
                    steps[index].classList.remove('pending');
                    transitionStep(index + 1);
                }, 4000); // advance active state every 4 seconds
            }
        };
        transitionStep(1); // Start with step 2 (index 1)

        // 2. Perform the actual API request
        const formData = new FormData();
        formData.append('file', file);

        fetch('/api/audit', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || `HTTP error! status: ${response.status}`);
                }).catch(() => {
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (progressTimer) {
                clearTimeout(progressTimer);
            }
            
            // Check for individual circular errors
            const result = data.results && data.results[0];
            if (!result) {
                throw new Error("Invalid or empty response format from audit API.");
            }
            if (result.error) {
                throw new Error(result.error);
            }

            handleAuditSuccess(result, file);
        })
        .catch(error => {
            if (progressTimer) {
                clearTimeout(progressTimer);
            }
            console.error('Audit failed:', error);
            handleAuditError(error.message);
        });
    }

    async function handleAuditSuccess(result, file) {
        const sleep = ms => new Promise(r => setTimeout(r, ms));

        // 1. Populate clause tags dynamically from actual clause text
        const keywords = ['shall', 'must', 'days', 'penalty', 'reporting', 'kyc', 'aml', 'capital', 'liquidity', 'governance', 'deadline', 'ensure', 'limit'];
        const foundTags = new Set();
        result.gaps.forEach(g => {
            keywords.forEach(kw => {
                if (g.clause_text.toLowerCase().includes(kw)) {
                    foundTags.add(kw);
                }
            });
        });
        if (foundTags.size === 0) {
            foundTags.add('obligation');
        }
        
        const tagsContainer = document.getElementById('clause-tags');
        tagsContainer.innerHTML = '';
        Array.from(foundTags).slice(0, 8).forEach(tagText => {
            const span = document.createElement('span');
            span.className = 'tag-pill highlight';
            span.textContent = tagText;
            tagsContainer.appendChild(span);
        });

        // 2. Populate policy chips dynamically from actual closest policy matches
        const policiesContainer = document.getElementById('policy-chips');
        policiesContainer.innerHTML = '';
        const seenPolicies = new Set();
        result.gaps.forEach(g => {
            if (g.best_policy_match && g.best_policy_match !== 'None found' && g.best_policy_match !== 'None') {
                const name = g.best_policy_match.split('\n')[0].replace(/[\#\*\_]/g, '').trim().substring(0, 28);
                const score = (g.similarity_score * 100).toFixed(0) + '%';
                const key = `${name}-${score}`;
                if (!seenPolicies.has(key)) {
                    seenPolicies.add(key);
                    const div = document.createElement('div');
                    div.className = 'policy-chip';
                    div.innerHTML = `<i data-lucide="file-check"></i> ${name} <span class="similarity-badge">${score}</span>`;
                    policiesContainer.appendChild(div);
                }
            }
        });
        
        if (policiesContainer.children.length === 0) {
            const div = document.createElement('div');
            div.className = 'policy-chip';
            div.innerHTML = `<i data-lucide="alert-triangle"></i> No policy matches found`;
            policiesContainer.appendChild(div);
        }
        lucide.createIcons({ root: policiesContainer });

        // 3. Score compliance gaps (Risk Meter)
        let maxScore = 0;
        result.gaps.forEach(g => {
            if (g.penalty_score > maxScore) {
                maxScore = g.penalty_score;
            }
        });
        const riskFill = document.getElementById('risk-fill');
        riskFill.style.width = `${maxScore}%`;

        // 4. Smoothly mark all steps as complete in sequence
        for (let i = 0; i < steps.length; i++) {
            steps[i].classList.remove('pending');
            steps[i].classList.add('complete');
            await sleep(150);
        }

        // 5. Render results table and charts
        renderResultsTable(result, file);

        // 6. Transition to results
        await sleep(1000);
        processingZone.classList.remove('active');
        setTimeout(() => {
            resultsZone.classList.add('active');
        }, 300);
    }

    function renderResultsTable(result, file) {
        // Cache the full gap list so chart clicks can re-filter without a re-fetch
        currentGaps = result.gaps || [];
        activeRiskFilter = null;
        renderFilteredTable();

        // Fix PDF Download Button (BUG 1)
        const downloadBtn = resultsZone.querySelector('.results-header .btn-secondary');
        const newDownloadBtn = downloadBtn.cloneNode(true);
        downloadBtn.parentNode.replaceChild(newDownloadBtn, downloadBtn);
        
        newDownloadBtn.addEventListener('click', () => {
            // BUG 1 fix: use result.circular_number returned from API if present, fallback to filename stem without extension
            const reportId = result.circular_number || file.name.replace(/\.[^/.]+$/, "");
            window.location.href = `/api/report/${encodeURIComponent(reportId)}`;
        });

        // Initialize Real Data Visualizations (FEATURE 1)
        initResultCharts(currentGaps);
    }

    // Renders the results table from currentGaps, respecting activeRiskFilter.
    // Also updates/creates a small "filtered by X" status bar above the table.
    function renderFilteredTable(highlightClause) {
        const tbody = document.querySelector('.results-table tbody');
        tbody.innerHTML = '';

        const gaps = activeRiskFilter
            ? currentGaps.filter(g => g.risk_band === activeRiskFilter)
            : currentGaps;

        renderFilterStatusBar();

        if (!gaps || gaps.length === 0) {
            const tr = document.createElement('tr');
            const emptyMessage = activeRiskFilter
                ? `No ${activeRiskFilter} severity gaps found.`
                : 'No compliance gaps detected! Existing policies fully cover all obligations.';
            const emptyIcon = activeRiskFilter ? 'filter-x' : 'party-popper';
            tr.innerHTML = `
                <td colspan="4" class="text-center" style="padding: 2.5rem; color: var(--text-secondary); font-weight: 500;">
                    <i data-lucide="${emptyIcon}" style="display: block; margin: 0 auto 0.5rem auto; width: 32px; height: 32px;"></i>
                    ${emptyMessage}
                </td>
            `;
            tbody.appendChild(tr);
            lucide.createIcons({ root: tbody });
            return;
        }

        // Sort gaps by penalty score descending
        const sortedGaps = [...gaps].sort((a, b) => b.penalty_score - a.penalty_score);

        sortedGaps.forEach(g => {
            const tr = document.createElement('tr');
            tr.dataset.clause = g.clause_text;
            const rawBand = g.risk_band.toLowerCase();
            const bandClass = rawBand === 'medium' ? 'med' : rawBand;
            const scoreDisplay = g.penalty_score.toFixed(1) + '/100';

            let statusHtml = `<span class="status-text gap">Policy Gap Detected</span>`;
            if (g.days_remaining !== null) {
                if (g.days_remaining <= 7) {
                    statusHtml = `<span class="status-text gap" style="color: var(--status-error); font-weight: 600;">Urgent: ${g.days_remaining} Days Left</span>`;
                } else {
                    statusHtml = `<span class="status-text gap" style="color: var(--status-warning);">${g.days_remaining} Days Left</span>`;
                }
            }

            // Clean best policy match display
            let policyHintHtml = '';
            if (g.best_policy_match && g.best_policy_match !== 'None found' && g.best_policy_match !== 'None') {
                const cleanPolicy = g.best_policy_match.split('\n')[0].replace(/[\#\*\_]/g, '').trim();
                policyHintHtml = `
                    <div class="policy-hint" style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 6px; display: flex; align-items: center; gap: 4px;">
                        <i data-lucide="git-compare" style="width: 12px; height: 12px; flex-shrink: 0;"></i>
                        <span>Closest policy match: <strong>${cleanPolicy}</strong> (Similarity: ${(g.similarity_score * 100).toFixed(0)}%)</span>
                    </div>
                `;
            }

            tr.innerHTML = `
                <td class="clause-cell">
                    <div style="font-family: var(--font-sans); line-height: 1.5;">"${g.clause_text}"</div>
                    ${policyHintHtml}
                </td>
                <td><span class="risk-pill ${bandClass}">${g.risk_band}</span></td>
                <td class="mono">${scoreDisplay}</td>
                <td>${statusHtml}</td>
            `;
            tbody.appendChild(tr);
        });
        lucide.createIcons({ root: tbody });

        // If a specific gap was just clicked from the priority chart, scroll to
        // it and flash a highlight so it's obvious which row matched the click.
        if (highlightClause) {
            const targetRow = Array.from(tbody.querySelectorAll('tr'))
                .find(row => row.dataset.clause === highlightClause);
            if (targetRow) {
                targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                targetRow.classList.add('row-flash-highlight');
                setTimeout(() => targetRow.classList.remove('row-flash-highlight'), 1800);
            }
        }
    }

    // Creates (once) or updates the small status bar shown above the results
    // table when a severity filter from the donut chart is active.
    function renderFilterStatusBar() {
        const tableResponsive = document.querySelector('#results-zone .table-responsive');
        let bar = document.getElementById('filter-status-bar');

        if (!activeRiskFilter) {
            if (bar) bar.remove();
            return;
        }

        const totalCount = currentGaps.length;
        const filteredCount = currentGaps.filter(g => g.risk_band === activeRiskFilter).length;
        const color = getSeverityColor(activeRiskFilter);

        if (!bar) {
            bar = document.createElement('div');
            bar.id = 'filter-status-bar';
            bar.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; margin-bottom: 12px; border-radius: var(--radius-md); background: var(--bg-tertiary); border: 1px solid rgba(255,255,255,0.05); font-size: 0.85rem;';
            tableResponsive.parentNode.insertBefore(bar, tableResponsive);
        }

        bar.innerHTML = `
            <span style="color: var(--text-secondary);">
                Showing <strong style="color: var(--text-primary);">${filteredCount}</strong> of ${totalCount} gaps
                &mdash; filtered to
                <span class="risk-pill ${activeRiskFilter.toLowerCase() === 'medium' ? 'med' : activeRiskFilter.toLowerCase()}" style="margin-left: 4px;">${activeRiskFilter}</span>
            </span>
            <button class="btn btn-text btn-small" id="clear-filter-btn" style="display: flex; align-items: center; gap: 4px;">
                <i data-lucide="x" style="width: 14px; height: 14px;"></i> Clear filter
            </button>
        `;
        lucide.createIcons({ root: bar });
        document.getElementById('clear-filter-btn').addEventListener('click', () => {
            activeRiskFilter = null;
            renderFilteredTable();
            if (severityChart) severityChart.update();
        });
    }

    // Chart.js helper for Risk Band colors
    function getSeverityColor(band) {
        switch (band.toLowerCase()) {
            case 'critical': return '#EF4444';
            case 'high': return '#F97316';
            case 'medium': return '#F59E0B';
            case 'low': return '#10B981';
            default: return '#3B82F6';
        }
    }

    function initResultCharts(gaps) {
        const themeColors = getThemeColors();

        // 1. Severity Chart (Doughnut)
        const severityCtx = document.getElementById('severity-chart').getContext('2d');
        if (severityChart) severityChart.destroy();

        const severityCounts = { Critical: 0, High: 0, Medium: 0, Low: 0 };
        gaps.forEach(g => {
            if (severityCounts[g.risk_band] !== undefined) {
                severityCounts[g.risk_band]++;
            }
        });

        severityChart = new Chart(severityCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(severityCounts),
                datasets: [{
                    data: Object.values(severityCounts),
                    backgroundColor: ['#EF4444', '#F97316', '#F59E0B', '#10B981'],
                    borderColor: themeColors.cardBg,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (!elements.length) return;
                    const idx = elements[0].index;
                    const clickedBand = Object.keys(severityCounts)[idx];
                    activeRiskFilter = (activeRiskFilter === clickedBand) ? null : clickedBand;
                    renderFilteredTable();
                },
                plugins: {
                    legend: {
                        position: 'right',
                        onClick: (evt, legendItem) => {
                            const clickedBand = legendItem.text;
                            activeRiskFilter = (activeRiskFilter === clickedBand) ? null : clickedBand;
                            renderFilteredTable();
                        },
                        labels: {
                            color: themeColors.text,
                            font: { family: 'Inter, sans-serif', size: 11 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            footer: () => 'Click a slice or legend item to filter the table below'
                        }
                    }
                }
            }
        });

        // 2. Priority Chart (Horizontal Bar Chart of Top 5 Gaps)
        const priorityCtx = document.getElementById('priority-chart').getContext('2d');
        if (priorityChart) priorityChart.destroy();

        const sortedGaps = [...gaps].sort((a, b) => b.penalty_score - a.penalty_score).slice(0, 5);
        const labels = sortedGaps.map(g => g.clause_text.substring(0, 25) + '...');
        const scores = sortedGaps.map(g => g.penalty_score);
        const barColors = sortedGaps.map(g => getSeverityColor(g.risk_band));

        priorityChart = new Chart(priorityCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Risk Score',
                    data: scores,
                    backgroundColor: barColors,
                    borderWidth: 0,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                onClick: (evt, elements) => {
                    if (!elements.length) return;
                    const idx = elements[0].index;
                    const clickedGap = sortedGaps[idx];
                    if (!clickedGap) return;
                    // Clear any active severity filter so the row is guaranteed visible
                    activeRiskFilter = null;
                    renderFilteredTable(clickedGap.clause_text);
                },
                onHover: (evt, elements) => {
                    evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                },
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        grid: { color: themeColors.grid },
                        ticks: { color: themeColors.text }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: themeColors.text }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const gap = sortedGaps[items[0].dataIndex];
                                return gap ? gap.clause_text : '';
                            },
                            footer: () => 'Click to jump to this row in the table below'
                        }
                    }
                }
            }
        });
    }

    // 6. Audit History View (FEATURE 2)
    const refreshHistoryBtn = document.getElementById('refresh-history-btn');
    refreshHistoryBtn.addEventListener('click', fetchAuditHistory);

    function fetchAuditHistory() {
        fetch('/api/history')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch history: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            auditHistoryData = data.history || [];
            renderHistoryTable();
            renderHistoryTimeline();
        })
        .catch(error => {
            console.error('Error fetching audit history:', error);
            const tbody = document.querySelector('.history-table tbody');
            tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--status-error); padding: 1.5rem;">Failed to load audit history: ${error.message}</td></tr>`;
        });
    }

    function renderHistoryTable() {
        const tbody = document.querySelector('.history-table tbody');
        tbody.innerHTML = '';

        if (auditHistoryData.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--text-muted); padding: 2rem;">No past runs found in the audit log.</td></tr>`;
            return;
        }

        // Sort audit history data
        const sorted = [...auditHistoryData].sort((a, b) => {
            let valA = a[currentSortField];
            let valB = b[currentSortField];
            
            if (valA === null || valA === undefined) valA = '';
            if (valB === null || valB === undefined) valB = '';

            if (typeof valA === 'string') {
                return currentSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            } else {
                return currentSortAsc ? valA - valB : valB - valA;
            }
        });

        sorted.forEach(item => {
            const tr = document.createElement('tr');
            
            // Format timestamp
            const date = new Date(item.timestamp);
            const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            let downloadHtml = '—';
            if (item.report_path) {
                downloadHtml = `
                    <a href="/api/report/${encodeURIComponent(item.circular_number)}" class="btn btn-secondary btn-small" style="padding: 4px 8px; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 4px;">
                        <i data-lucide="download" style="width: 12px; height: 12px;"></i> PDF
                    </a>
                `;
            }

            tr.innerHTML = `
                <td>${formattedDate}</td>
                <td class="mono">${item.circular_number}</td>
                <td><span class="status-badge" style="background: rgba(0, 91, 112, 0.12); color: var(--accent-teal-light); border: 1px solid rgba(0, 122, 150, 0.2); font-size: 0.78rem;">${item.regulator}</span></td>
                <td>${item.obligations_found}</td>
                <td><span style="color: ${item.gaps_detected > 0 ? 'var(--status-error)' : 'var(--status-success)'}; font-weight: 500;">${item.gaps_detected}</span></td>
                <td class="mono">${item.avg_penalty_score.toFixed(1)}/100</td>
                <td>${downloadHtml}</td>
            `;
            tbody.appendChild(tr);
        });

        lucide.createIcons({ root: tbody });
    }

    function renderHistoryTimeline() {
        const themeColors = getThemeColors();
        const historyCtx = document.getElementById('history-timeline-chart').getContext('2d');
        
        if (historyTimelineChart) historyTimelineChart.destroy();

        if (auditHistoryData.length === 0) return;

        // Oldest to newest for timeline line chart
        const sortedHistoryForChart = [...auditHistoryData].reverse();
        
        const labels = sortedHistoryForChart.map(item => {
            const d = new Date(item.timestamp);
            return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
        });
        
        const gapsData = sortedHistoryForChart.map(item => item.gaps_detected);
        const penaltyData = sortedHistoryForChart.map(item => item.avg_penalty_score);

        historyTimelineChart = new Chart(historyCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Gaps Detected',
                        data: gapsData,
                        borderColor: '#EF4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Avg Penalty Score',
                        data: penaltyData,
                        borderColor: '#F59E0B',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.25,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: themeColors.grid },
                        ticks: { color: themeColors.text }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: themeColors.text }
                    },
                    x: {
                        grid: { color: themeColors.grid },
                        ticks: { color: themeColors.text }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: themeColors.text }
                    }
                }
            }
        });
    }

    // Set sorting columns click event listeners
    function sortHistory(field) {
        if (currentSortField === field) {
            currentSortAsc = !currentSortAsc;
        } else {
            currentSortField = field;
            currentSortAsc = true;
        }
        renderHistoryTable();
    }

    document.getElementById('sort-timestamp').addEventListener('click', () => sortHistory('timestamp'));
    document.getElementById('sort-circular').addEventListener('click', () => sortHistory('circular_number'));
    document.getElementById('sort-regulator').addEventListener('click', () => sortHistory('regulator'));
    document.getElementById('sort-obligations').addEventListener('click', () => sortHistory('obligations_found'));
    document.getElementById('sort-gaps').addEventListener('click', () => sortHistory('gaps_detected'));
    document.getElementById('sort-penalty').addEventListener('click', () => sortHistory('avg_penalty_score'));

    function handleAuditError(messageText) {
        errorMessage.textContent = messageText || "An unexpected error occurred during the audit.";
        
        // Hide processing, show error
        processingZone.classList.remove('active');
        setTimeout(() => {
            errorZone.classList.add('active');
            lucide.createIcons({ root: errorZone });
        }, 300);
    }
});