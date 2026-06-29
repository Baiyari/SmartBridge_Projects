/* 
  =========================================
  SEO Audit Agent - Core Logic & Interactions
  =========================================
*/

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide Icons
  lucide.createIcons();

  // Initialize all interactive modules
  initScrollReveal();
  initTerminalSimulator();
  initExpandableCards();
  initDashboardFilter();
  initHowItWorksTimeline();
  
  // New upgraded interactions (Phase 2)
  initInteractiveAuditForm();
  initFooterTabsAndThemes();
});

/* =========================================
   1. SCROLL REVEAL ANIMATION (Intersection Observer)
   ========================================= */
function initScrollReveal() {
  const reveals = document.querySelectorAll(".reveal");
  
  const revealCallback = (entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("active");
        
        // Trigger viewport-specific counting/gauge animations
        if (entry.target.id === "demo-left-text" || entry.target.id === "demo-stats-counters") {
          triggerStatCounters();
        }
        if (entry.target.id === "demo-right-graphic") {
          triggerPipelineFlow();
        }
        if (entry.target.id === "dash-preview-card") {
          triggerScoreGauge();
        }
      }
    });
  };

  const observer = new IntersectionObserver(revealCallback, {
    root: null,
    threshold: 0.15,
    rootMargin: "0px"
  });

  reveals.forEach(element => observer.observe(element));
}

/* =========================================
   2. HERO TERMINAL EMULATOR LOOP (Laptop Mockup)
   ========================================= */
function initTerminalSimulator() {
  showTerminalReadyState();
}

function showTerminalReadyState() {
  const terminal = document.getElementById("hero-terminal");
  if (!terminal) return;

  terminal.innerHTML = "";

  const bootLines = [
    { html: `<span style="color: var(--term-green)">[SYSTEM] Booting SEO Audit Agent — core module initialisation...</span>`, delay: 0 },
    { html: `<span style="color: var(--term-green)">[CRAWLER]</span> Async HTML fetcher &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&rarr; <span style="color: var(--term-green); font-weight:700;">online</span>`, delay: 420 },
    { html: `<span style="color: var(--term-purple)">[NLP]</span> &nbsp;&nbsp;&nbsp; Readability + keyword engine &rarr; <span style="color: var(--term-green); font-weight:700;">loaded</span>`, delay: 860 },
    { html: `<span style="color: var(--term-green)">[LINKS]</span> &nbsp; Broken link monitor &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&rarr; <span style="color: var(--term-green); font-weight:700;">armed</span>`, delay: 1280 },
    { html: `<span style="color: var(--term-purple)">[REPORT]</span> Google Sheets sync &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&rarr; <span style="color: var(--term-green); font-weight:700;">connected</span>`, delay: 1700 },
    { html: `&nbsp;`, delay: 2080 },
    { html: `<span style="color: var(--term-green); font-weight:800; letter-spacing:0.04em;">&#9654; All systems READY. Agent is standing by.</span>`, delay: 2200 },
    { html: `&nbsp;`, delay: 2560 },
    { html: `<span class="term-prompt">admin@seo-agent:~$ </span><span class="cursor"></span>`, delay: 2700 },
  ];

  bootLines.forEach(({ html, delay }) => {
    setTimeout(() => {
      if (!document.getElementById("hero-terminal")) return;
      const line = document.createElement("div");
      line.className = "terminal-line";
      line.innerHTML = html;
      terminal.appendChild(line);
      terminal.scrollTop = terminal.scrollHeight;
    }, delay);
  });
}

/* =========================================
   3. SOLUTIONS FEATURE CARDS EXPANSION
   ========================================= */
function initExpandableCards() {
  const cards = document.querySelectorAll(".semrush-card");

  cards.forEach(card => {
    const btn = card.querySelector(".card-expand-btn");
    if (!btn) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      
      const isExpanded = card.classList.contains("expanded");
      
      cards.forEach(c => {
        c.classList.remove("expanded");
      });

      if (!isExpanded) {
        card.classList.add("expanded");
        
        const cardType = btn.getAttribute("data-card");
        if (cardType === "keywords") {
          animateKeywordBarChart();
        }
      }
    });
  });

  function animateKeywordBarChart() {
    const bars = document.querySelectorAll("#bar-chart-keywords-mini .bar-pill");
    bars.forEach(bar => {
      const targetHeight = bar.style.height;
      bar.style.height = "0%";
      setTimeout(() => {
        bar.style.height = targetHeight;
      }, 100);
    });
  }
}

/* =========================================
   4. CONCURRENT PIPELINE FLOW & COUNTERS
   ========================================= */
let statCountersTriggered = false;
let pipelineTriggered = false;

function triggerStatCounters() {
  if (statCountersTriggered) return;
  statCountersTriggered = true;

  animateNumber("count-pages", 0, 200, 1500, " pages");
  animateNumber("count-checks", 0, 5, 1000, " checks");
  animateNumber("count-groq", 0.0, 1.8, 1200, "s response", true, "< ");
}

function triggerPipelineFlow() {
  if (pipelineTriggered) return;
  pipelineTriggered = true;

  animateNumber("viz-crawled-num", 0, 147, 3000);
  animateNumber("viz-issues-num", 0, 312, 3000);
  animateNumber("viz-llm-num", 0, 147, 3000);
  animateNumber("viz-score-num", 0, 74, 3000, "/100");

  const container = document.getElementById("particles-track-overlay");
  const nodes = [
    document.getElementById("node-crawl"),
    document.getElementById("node-meta"),
    document.getElementById("node-keywords"),
    document.getElementById("node-readability"),
    document.getElementById("node-links"),
    document.getElementById("node-llm"),
    document.getElementById("node-sheets")
  ];

  function spawnParticle() {
    if (!container) return;

    const categories = ["green", "amber", "red"];
    const category = categories[Math.floor(Math.random() * categories.length)];
    
    const particle = document.createElement("div");
    particle.className = `particle particle-${category}`;
    container.appendChild(particle);

    let step = 0;
    const stepDuration = 550;

    function move() {
      if (step >= nodes.length) {
        particle.remove();
        return;
      }

      const currentNode = nodes[step];
      if (currentNode) {
        currentNode.classList.add("active");
        setTimeout(() => {
          currentNode.classList.remove("active");
        }, 300);

        const nodeRect = currentNode.offsetLeft + currentNode.offsetWidth / 2;
        particle.style.left = `${nodeRect - 4}px`;
      }

      step++;
      setTimeout(move, stepDuration);
    }

    move();
  }

  setInterval(spawnParticle, 2000);
  
  const bars = document.querySelectorAll("#active-bars-visual .rising-bar");
  setInterval(() => {
    bars.forEach(bar => {
      const randomHeight = Math.floor(Math.random() * 85) + 15;
      bar.style.height = `${randomHeight}%`;
    });
  }, 1000);
}

function animateNumber(id, start, end, duration, suffix = "", isFloat = false, prefix = "") {
  const element = document.getElementById(id);
  if (!element) return;

  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 3);
    
    let currentVal;
    if (isFloat) {
      currentVal = (start + (end - start) * easeProgress).toFixed(1);
    } else {
      currentVal = Math.floor(start + (end - start) * easeProgress);
    }

    element.textContent = prefix + currentVal + suffix;

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = prefix + end + suffix;
    }
  }

  requestAnimationFrame(update);
}

/* =========================================
   5. VISIBILITY REPORT GAUGE & DASHBOARD FILTER
   ========================================= */
let gaugeTriggered = false;

function updateGaugeColor(element, score) {
  element.classList.remove("gauge-red", "gauge-yellow", "gauge-green");
  if (score >= 75) {
    element.classList.add("gauge-green");
  } else if (score >= 50) {
    element.classList.add("gauge-yellow");
  } else {
    element.classList.add("gauge-red");
  }
}

function triggerScoreGauge() {
  if (gaugeTriggered) return;
  gaugeTriggered = true;

  const fill = document.getElementById("gauge-fill-circle");
  if (!fill) return;

  const scoreText = document.getElementById("gauge-score-value");
  const score = scoreText ? parseInt(scoreText.textContent) || 74 : 74;
  updateGaugeColor(fill, score);

  const targetOffset = 440 - (score / 100) * 440;
  
  setTimeout(() => {
    fill.style.strokeDashoffset = targetOffset;
  }, 300);
}

function initDashboardFilter() {
  const filterSelect = document.getElementById("issue-filter-select");
  const tableRowsContainer = document.getElementById("issues-table-rows");
  if (!filterSelect || !tableRowsContainer) return;

  const pills = document.querySelectorAll("#issue-pill-filter .filter-pill");
  pills.forEach(pill => {
    pill.addEventListener("click", () => {
      pills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      
      const val = pill.getAttribute("data-value");
      filterSelect.value = val;
      filterSelect.dispatchEvent(new Event("change"));
    });
  });

  const dataset = {
    all: [
      { url: "/", score: 78, scoreClass: "badge-excellent", meta: "0 errors", links: "0 dead", readability: "Standard (68)" },
      { url: "/blog/seo-tips", score: 54, scoreClass: "badge-critical", meta: "2 errors (Desc)", links: "4 dead links", readability: "Low (42)" },
      { url: "/about", score: 92, scoreClass: "badge-excellent", meta: "0 errors", links: "0 dead", readability: "Excellent (82)" },
      { url: "/pricing", score: 72, scoreClass: "badge-warning", meta: "1 error (Title)", links: "8 dead links", readability: "Standard (65)" }
    ],
    critical: [
      { url: "/blog/seo-tips", score: 54, scoreClass: "badge-critical", meta: "2 errors (Desc)", links: "4 dead links", readability: "Low (42)" },
      { url: "/pricing", score: 72, scoreClass: "badge-warning", meta: "1 error (Title)", links: "8 dead links", readability: "Standard (65)" }
    ],
    links: [
      { url: "/blog/seo-tips", score: 54, scoreClass: "badge-critical", meta: "—", links: "4 dead (404 status)", readability: "—" },
      { url: "/pricing", score: 72, scoreClass: "badge-warning", meta: "—", links: "8 dead (404 status)", readability: "—" }
    ],
    meta: [
      { url: "/blog/seo-tips", score: 54, scoreClass: "badge-critical", meta: "Missing description, absent OG tag", links: "—", readability: "—" },
      { url: "/pricing", score: 72, scoreClass: "badge-warning", meta: "Missing Title tag", links: "—", readability: "—" }
    ],
    readability: [
      { url: "/blog/seo-tips", score: 54, scoreClass: "badge-critical", meta: "—", links: "—", readability: "Gunning Fog grade 15 (Low)" }
    ]
  };

  window.seoDataset = dataset;

  function renderTable(filter) {
    tableRowsContainer.innerHTML = "";
    const items = window.seoDataset[filter] || [];

    if (items.length === 0) {
      tableRowsContainer.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding: 24px;">No issues matching this filter criteria.</td></tr>`;
      return;
    }

    items.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-size: 0.8rem; font-weight:600;">${item.url}</td>
        <td><span class="table-score-badge ${item.scoreClass}">${item.score}/100</span></td>
        <td style="color: ${item.meta.includes("errors") || item.meta.includes("Missing") || (item.meta.includes("error") && !item.meta.startsWith("0")) ? "var(--color-critical)" : "inherit"}">${item.meta}</td>
        <td style="color: ${item.links.includes("dead") && !item.links.startsWith("0") ? "var(--color-critical)" : "inherit"}">${item.links}</td>
        <td>${item.readability}</td>
      `;
      tableRowsContainer.appendChild(tr);
    });
  }

  window.renderSeoTable = renderTable;

  filterSelect.addEventListener("change", (e) => {
    renderTable(e.target.value);
  });

  renderTable("all");
}

/* =========================================
   6. HOW IT WORKS TIMELINE DYNAMIC STATE
   ========================================= */
function initHowItWorksTimeline() {
  const steps = document.querySelectorAll(".timeline-step");
  const activeTimeline = document.getElementById("active-timeline-progress");
  const illIcon = document.getElementById("ill-card-icon");
  const illTitle = document.getElementById("ill-card-title");
  const illDesc = document.getElementById("ill-card-desc");

  const stepDetails = {
    1: {
      icon: "terminal",
      title: "Step 1 — Submit URL Target",
      desc: "Execute the command line client python main.py --url yoursite.com pointing directly to your domain target. Standardizes configuration parameters instantly."
    },
    2: {
      icon: "compass",
      title: "Step 2 — Async BFS Crawl",
      desc: "The autonomous agent initiates a Breadth-First Search. Utilizing Python asyncio, it maps internal pathways concurrently, ignoring outside subdomains."
    },
    3: {
      icon: "bar-chart-2",
      title: "Step 3 — Parallel Analyzers",
      desc: "5 individual checkers run asynchronously per page. The script parses meta-structures, densities, word indexes, anchor elements, and readability grades in parallel."
    },
    4: {
      icon: "brain",
      title: "Step 4 — Ollama LLM AI Scoring",
      desc: "Ollama (Mistral) parses accumulated page faults. Rather than raw counts, it processes issues in one payload context and formulates semantic markdown remedies."
    },
    5: {
      icon: "table",
      title: "Step 5 — Synchronize Google Sheets",
      desc: "Audit logs are batched and pushed instantly using Google Service Account credentials. Row values stack over time, allowing clear trend dashboards."
    }
  };

  steps.forEach(step => {
    step.addEventListener("click", () => {
      const stepIndex = parseInt(step.getAttribute("data-step"));

      steps.forEach(s => s.classList.remove("active"));
      steps.forEach(s => {
        const idx = parseInt(s.getAttribute("data-step"));
        if (idx <= stepIndex) {
          s.classList.add("active");
        }
      });

      const percentage = (stepIndex - 1) * 25;
      if (activeTimeline) {
        activeTimeline.style.width = `${percentage}%`;
      }

      const details = stepDetails[stepIndex];
      if (details && illIcon && illTitle && illDesc) {
        illIcon.innerHTML = `<i data-lucide="${details.icon}" style="width: 32px; height: 32px;"></i>`;
        illTitle.textContent = details.title;
        illDesc.textContent = details.desc;
        lucide.createIcons();
      }
    });
  });
}

/* =========================================
   7. INTERACTIVE AUDIT FORM — REAL BACKEND
   ========================================= */
function initInteractiveAuditForm() {
  const form = document.getElementById("hero-audit-form");
  const urlField = document.getElementById("hero-url-field");
  const submitBtn = document.getElementById("hero-submit-btn");
  const btnText = document.getElementById("hero-btn-text");
  const btnSpinner = document.getElementById("hero-btn-spinner");
  
  const resultsCard = document.getElementById("hero-results-card");
  const gaugeFill = document.getElementById("results-gauge-fill");
  const viewReportBtn = document.getElementById("results-view-report-btn");

  if (!form || !urlField || !submitBtn) return;

  const BACKEND = "";
  const terminal = document.getElementById("hero-terminal");

  function printLine(text, isSuccess = false, isError = false) {
    if (!terminal) return;
    const lineDiv = document.createElement("div");
    lineDiv.className = "terminal-line";
    if (isSuccess) { lineDiv.style.color = "#00FF88"; lineDiv.style.fontWeight = "700"; }
    if (isError)   { lineDiv.style.color = "#FF5555"; lineDiv.style.fontWeight = "700"; }
    lineDiv.textContent = text;
    terminal.appendChild(lineDiv);
    terminal.scrollTop = terminal.scrollHeight;
  }

  function resetButton() {
    submitBtn.disabled = false;
    btnText.textContent = "Run Free Audit";
    btnSpinner.style.display = "none";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const enteredUrl = urlField.value.trim();
    if (!enteredUrl) return;

    let formattedUrl = enteredUrl;
    if (!/^https?:\/\//i.test(formattedUrl)) formattedUrl = "https://" + formattedUrl;

    submitBtn.disabled = true;
    btnText.textContent = "Crawling...";
    btnSpinner.style.display = "inline-block";
    resultsCard.classList.remove("visible");
    if (gaugeFill) gaugeFill.style.strokeDashoffset = "440";
    
    if (terminal) {
      terminal.innerHTML = "";
      // Type command
      const cmdLine = document.createElement("div");
      cmdLine.className = "terminal-line";
      cmdLine.innerHTML = `<span class="term-prompt">admin@seo-agent:~$ </span><span class="term-cmd">python main.py --url ${formattedUrl}</span>`;
      terminal.appendChild(cmdLine);
    }

    printLine(`[INFO] Connecting to SEO Audit Agent backend...`);

    try {
      await fetch(`${BACKEND}/health`);
    } catch {
      printLine(`✗ Cannot reach backend at ${BACKEND}. Is api.py running?`, false, true);
      printLine(`  → Run: py api.py inside seo_agent/seo_agent directory`, false, true);
      resetButton();
      return;
    }

    printLine(`[INFO] Initialising crawler for ${formattedUrl}...`);

    const progressLines = [
      `[INFO] Crawling pages (BFS async)...`,
      `[INFO] Running meta tag checks...`,
      `[INFO] Analysing keyword density...`,
      `[INFO] Scoring readability (Flesch-Kincaid)...`,
      `[INFO] Detecting broken links...`,
      `[INFO] Sending issues context to Ollama (mistral) LLM...`,
      `[INFO] Generating prioritised suggestions...`,
      `[INFO] Writing report sheets to Google Sheets...`,
    ];
    let pIdx = 0;
    const progressTimer = setInterval(() => {
      if (pIdx < progressLines.length) printLine(progressLines[pIdx++]);
    }, 2500);

    let results;
    try {
      const resp = await fetch(`${BACKEND}/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ url: formattedUrl }),
      });

      clearInterval(progressTimer);

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        if (resp.status === 401) {
          printLine(`✗ Please sign in first to run an audit.`, false, true);
          resetButton();
          openAuthModal();
          return;
        }
        printLine(`✗ Audit failed: ${err.error || resp.statusText}`, false, true);
        resetButton();
        return;
      }

      results = await resp.json();
    } catch (err) {
      clearInterval(progressTimer);
      printLine(`✗ Request error: ${err.message}`, false, true);
      resetButton();
      return;
    }

    const totalPages  = results.length;
    const avgScore    = totalPages
      ? Math.round(results.reduce((s, r) => s + r.score, 0) / totalPages)
      : 0;
    const totalIssues = results.reduce((s, r) => s + r.meta_issues + r.broken_links, 0);

    printLine(`[SUCCESS] Audit complete. ${totalPages} pages audited. Average score: ${avgScore}/100.`, true);
    printLine(`[SUCCESS] Google Sheet report successfully updated.`, true);

    showRealResults(results, avgScore, totalPages, totalIssues);
    resetButton();
  });

  function showRealResults(results, avgScore, totalPages, totalIssues) {
    const pagesEl      = document.getElementById("pill-pages-val");
    const issuesEl     = document.getElementById("pill-issues-val");
    const scoreEl      = document.getElementById("pill-score-val");
    const gaugeNum     = document.getElementById("results-gauge-num");
    const pagesStatEl  = document.querySelector(".results-card-stat-box:nth-child(1) .results-card-stat-val");
    const issuesStatEl = document.querySelector(".results-card-stat-box:nth-child(2) .results-card-stat-val");

    if (pagesEl)      pagesEl.textContent  = `${totalPages} pages`;
    if (issuesEl)     issuesEl.textContent = `${totalIssues} errors`;
    if (scoreEl)      scoreEl.textContent  = `${avgScore} / 100`;
    if (gaugeNum)     gaugeNum.textContent = avgScore;
    if (pagesStatEl)  pagesStatEl.textContent  = totalPages;
    if (issuesStatEl) issuesStatEl.textContent = totalIssues;

    const topFixEl  = document.querySelector(".results-card-issue-val");
    const worstPage = results.sort((a, b) => a.score - b.score)[0];
    if (topFixEl && worstPage?.suggestions?.length) {
      let rawFix = worstPage.suggestions[0];

      // Handle dict-like strings: {'priority': 'CRITICAL', 'action': 'Add <title> tag'}
      const dictMatch = rawFix.match(/['"]action['"]\s*:\s*['"]([^'"]+)['"]/i);
      if (dictMatch) {
        const priority = rawFix.match(/['"]priority['"]\s*:\s*['"]([^'"]+)['"]/i);
        rawFix = (priority ? `[${priority[1].toUpperCase()}] ` : "") + dictMatch[1];
      }

      // Handle JSON object strings: {"priority":"HIGH","action":"..."}
      try {
        const parsed = JSON.parse(rawFix);
        if (parsed && parsed.action) {
          rawFix = (parsed.priority ? `[${parsed.priority.toUpperCase()}] ` : "") + parsed.action;
        }
      } catch (_) {}

      // Strip any leftover bracket tags like [CRITICAL] for a clean display
      const tagMatch = rawFix.match(/^\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+)$/i);
      const priorityLabel = tagMatch ? tagMatch[1].toUpperCase() : null;
      const fixText = (tagMatch ? tagMatch[2] : rawFix).replace(/</g, "&lt;").replace(/>/g, "&gt;");

      topFixEl.innerHTML = priorityLabel
        ? `<span style="color: var(--color-critical); font-weight:800;">[${priorityLabel}]</span> ${fixText}`
        : fixText;
    }

    const targetOffset = 440 - (avgScore / 100) * 440;
    if (gaugeFill) {
      updateGaugeColor(gaugeFill, avgScore);
      setTimeout(() => { gaugeFill.style.strokeDashoffset = targetOffset; }, 200);
    }
    const dashGaugeFill = document.getElementById("gauge-fill-circle");
    const dashGaugeValue = document.getElementById("gauge-score-value");
    if (dashGaugeValue) {
      dashGaugeValue.textContent = avgScore;
    }
    if (dashGaugeFill) {
      updateGaugeColor(dashGaugeFill, avgScore);
      dashGaugeFill.style.strokeDashoffset = targetOffset;
    }

    // Dynamic warning descriptor
    const warnHeadline = document.getElementById("score-warning-headline");
    const warnDesc = document.querySelector(".score-meta-desc p");
    const totalMetaIssues = results.reduce((s, r) => s + r.meta_issues, 0);
    const totalBrokenLinks = results.reduce((s, r) => s + r.broken_links, 0);

    if (warnHeadline) {
      warnHeadline.textContent = avgScore >= 75 ? "Excellent SEO Rating" : (avgScore >= 50 ? "Needs Optimization Work" : "Critical Fixes Required");
    }
    if (warnDesc) {
      warnDesc.innerHTML = `Your technical crawler performance is scored at ${avgScore}/100, but <strong>${totalMetaIssues} critical metadata issues</strong> and <strong>${totalBrokenLinks} broken links</strong> are affecting search visibility indexes.`;
    }

    // Rebuild dataset & render table
    if (window.seoDataset && window.renderSeoTable) {
      window.seoDataset.all = results.map(r => ({
        url: r.url,
        score: r.score,
        scoreClass: r.score >= 75 ? "badge-excellent" : (r.score >= 50 ? "badge-warning" : "badge-critical"),
        meta: r.meta_issues === 0 ? "0 errors" : `${r.meta_issues} error(s)`,
        links: r.broken_links === 0 ? "0 dead" : `${r.broken_links} dead link(s)`,
        readability: r.readability
      }));

      window.seoDataset.critical = window.seoDataset.all.filter(item => item.score < 75);
      window.seoDataset.links = window.seoDataset.all.filter(item => !item.links.startsWith("0"));
      window.seoDataset.meta = window.seoDataset.all.filter(item => !item.meta.startsWith("0"));
      window.seoDataset.readability = window.seoDataset.all.filter(item => item.readability.toLowerCase().includes("low") || item.score < 60);

      const activeFilter = document.querySelector("#issue-pill-filter .filter-pill.active")?.getAttribute("data-value") || "all";
      window.renderSeoTable(activeFilter);
    }

    // Rebuild Prioritized Actions
    const wrap = document.getElementById("priority-items-wrap");
    if (wrap) {
      wrap.innerHTML = "";
      const suggestionsMap = {};
      results.forEach(r => {
        if (r.suggestions && r.suggestions.length) {
          r.suggestions.forEach(s => {
            const match = s.match(/^\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.*)$/i);
            if (match) {
              const prio = match[1].toUpperCase();
              const text = match[2];
              const key = prio + "::" + text;
              if (!suggestionsMap[key]) {
                suggestionsMap[key] = {
                  prio: prio.toLowerCase(),
                  text: text,
                  count: 0
                };
              }
              suggestionsMap[key].count++;
            }
          });
        }
      });

      const groupedSuggestions = Object.values(suggestionsMap);
      const prioRank = { critical: 4, high: 3, medium: 2, low: 1 };
      groupedSuggestions.sort((a, b) => prioRank[b.prio] - prioRank[a.prio]);

      if (groupedSuggestions.length === 0) {
        wrap.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); padding: 24px;">
            ✓ All pages passed basic SEO validation. No critical actions needed!
          </div>
        `;
      } else {
        function getSuggestionDesc(text, moduleName) {
          if (moduleName === "Meta Module") return "Optimizing metadata is essential for search engine crawling and search bot indexing.";
          if (moduleName === "Links Module") return "Fixing broken links prevents crawl errors and improves user experience navigation.";
          if (moduleName === "Keyword Module") return "Adjusting keyword usage ensures search relevancy and prevents spam penalties.";
          if (moduleName === "Readability Module") return "Legible content increases on-page time and aligns with search readability algorithms.";
          return "AI generated optimization action to improve page visibility.";
        }

        groupedSuggestions.slice(0, 4).forEach((item, index) => {
          let moduleName = "General Module";
          if (/title|desc|canonical|og:|meta/i.test(item.text)) moduleName = "Meta Module";
          else if (/link|url|redirect|href/i.test(item.text)) moduleName = "Links Module";
          else if (/keyword|density|stuffing|overstuffed/i.test(item.text)) moduleName = "Keyword Module";
          else if (/readability|reading|grade|difficulty|flesch|fog/i.test(item.text)) moduleName = "Readability Module";

          const title = item.count > 1 ? `${item.text} on ${item.count} pages` : item.text;
          const desc = getSuggestionDesc(item.text, moduleName);
          const icon = item.prio === "critical" ? "alert-octagon" : (item.prio === "high" ? "alert-triangle" : (item.prio === "medium" ? "info" : "check-circle"));
          
          const div = document.createElement("div");
          div.className = `priority-item ${item.prio}`;
          div.id = `prio-real-${index}`;
          div.innerHTML = `
            <div class="priority-item-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="priority-badge-icon"><i data-lucide="${icon}" style="width: 14px; height: 14px;"></i></span>
                <span class="priority-badge ${item.prio}">${item.prio.toUpperCase()}</span>
              </div>
              <span style="font-size: 0.72rem; color: var(--text-muted);">${moduleName}</span>
            </div>
            <div class="priority-item-title">${title}</div>
            <div class="priority-item-desc">${desc}</div>
          `;
          wrap.appendChild(div);
        });
        
        lucide.createIcons();
      }
    }

    resultsCard.classList.add("visible");
    resultsCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (viewReportBtn) {
    viewReportBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetSec = document.getElementById("dashboard-sec");
      if (targetSec) {
        targetSec.scrollIntoView({ behavior: "smooth" });
      }
    });
  }
}

/* =========================================
   8. FOOTER SPECIFICATIONS TABS & THEMES
   ========================================= */
function initFooterTabsAndThemes() {
  const tabs = document.querySelectorAll(".tab-btn");
  const panes = document.querySelectorAll(".tab-pane");

  if (!tabs || !panes) return;

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetTab = tab.getAttribute("data-tab");
      const targetPane = document.getElementById(`pane-${targetTab}`);

      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      panes.forEach(p => {
        p.classList.remove("active");
      });

      if (targetPane) {
        targetPane.classList.add("active");
      }
    });
  });

  const themeButtons = document.querySelectorAll("#specs-theme-selectors .theme-card-btn");
  
  themeButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const theme = btn.getAttribute("data-theme");

      themeButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      document.body.classList.remove("dark-theme", "terminal-theme");

      if (theme === "dark") {
        document.body.classList.add("dark-theme");
      } else if (theme === "terminal") {
        document.body.classList.add("terminal-theme");
      }
    });
  });
}

/* =========================================
   AUTH — Login / Signup
   ========================================= */
let authMode = "login";

async function checkAuth() {
  try {
    const res = await fetch("/api/me", { credentials: "include" });
    const data = await res.json();
    if (data.email) {
      document.getElementById("nav-user-email").textContent = data.email;
      document.getElementById("nav-user-email").style.display = "inline";
      document.getElementById("nav-login-btn").style.display = "none";
      document.getElementById("nav-logout-btn").style.display = "inline";
    }
  } catch (e) { /* server not running locally — silently ignore */ }
}

function openAuthModal() {
  document.getElementById("auth-modal").style.display = "flex";
  document.getElementById("auth-error").textContent = "";
}

function closeAuthModal() {
  document.getElementById("auth-modal").style.display = "none";
}

function toggleAuthMode() {
  authMode = authMode === "login" ? "signup" : "login";
  document.getElementById("auth-title").textContent = authMode === "login" ? "Sign In" : "Create Account";
  document.getElementById("auth-submit-btn").textContent = authMode === "login" ? "Continue" : "Create Account";
  document.getElementById("auth-toggle").innerHTML = authMode === "login"
    ? 'Don\'t have an account? <span style="color:#7c3aed;">Sign up</span>'
    : 'Already have an account? <span style="color:#7c3aed;">Sign in</span>';
  document.getElementById("auth-error").textContent = "";
}

async function submitAuth() {
  const email = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  const errorEl = document.getElementById("auth-error");

  if (!email || !password) {
    errorEl.textContent = "Please fill in all fields.";
    return;
  }

  const endpoint = authMode === "login" ? "/api/login" : "/api/signup";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (res.ok) {
      closeAuthModal();
      checkAuth();
    } else {
      errorEl.textContent = data.error || "Something went wrong.";
    }
  } catch (e) {
    errorEl.textContent = "Could not connect to server.";
  }
}

async function logoutUser() {
  await fetch("/api/logout", { method: "POST", credentials: "include" });
  location.reload();
}

// Close modal on backdrop click
document.getElementById("auth-modal").addEventListener("click", function (e) {
  if (e.target === this) closeAuthModal();
});

// Check login state on page load
checkAuth();