function getLocalTodayISO() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

document.addEventListener("DOMContentLoaded", () => {

    loadDashboardStats();
    loadNewsTable();
    loadTodayNews();
    loadEarlierNews();
    loadMonitoredSites();
    loadSubscribers();
    loadAnalytics();
    loadScanLogs();
    setupEventListeners();
    setupTabSwitching();
});

let currentProvinceFilter = "Tất cả";
let currentEntityTypeFilter = "Tất cả";
let currentSearchQuery = "";
let currentDateFrom = "";
let currentDateTo = "";
let autoRefreshTimer = null;
let currentModalItem = null;

function setupTabSwitching() {
    const tabBtns = document.querySelectorAll(".tab-btn");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    const content = document.getElementById(tabId);
    
    if (btn) btn.classList.add("active");
    if (content) content.classList.add("active");

    if (tabId === "tab-today") loadTodayNews();
    if (tabId === "tab-sites") loadMonitoredSites();
    if (tabId === "tab-analytics") loadAnalytics();
    if (tabId === "tab-logs") loadScanLogs();
    if (tabId === "tab-news") loadNewsTable();
}

function setupEventListeners() {
    // Date Pickers
    const startDateInput = document.getElementById("startDate");
    if (startDateInput) {
        startDateInput.addEventListener("change", (e) => {
            currentDateFrom = e.target.value;
            loadNewsTable();
        });
    }

    const endDateInput = document.getElementById("endDate");
    if (endDateInput) {
        endDateInput.addEventListener("change", (e) => {
            currentDateTo = e.target.value;
            loadNewsTable();
        });
    }

    // Province filter select
    const provSelect = document.getElementById("provinceFilter");
    if (provSelect) {
        provSelect.addEventListener("change", (e) => {
            currentProvinceFilter = e.target.value;
            loadNewsTable();
        });
    }

    // Entity Type filter select
    const entSelect = document.getElementById("entityTypeFilter");
    if (entSelect) {
        entSelect.addEventListener("change", (e) => {
            currentEntityTypeFilter = e.target.value;
            loadNewsTable();
        });
    }


    // Search input
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        let timeout = null;
        searchInput.addEventListener("input", (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentSearchQuery = e.target.value.trim();
                loadNewsTable();
            }, 300);
        });
    }

    // Auto Refresh Toggle
    const chkAuto = document.getElementById("chkAutoRefresh");
    if (chkAuto) {
        chkAuto.addEventListener("change", (e) => {
            if (e.target.checked) {
                showToast("🔄 Đã bật chế độ Tự động làm mới dữ liệu (mỗi 30s)", "info");
                autoRefreshTimer = setInterval(() => {
                    loadDashboardStats();
                    loadNewsTable();
                    loadTodayNews();
                }, 30000);
            } else {
                showToast("⏸️ Đã tắt Tự động làm mới", "info");
                if (autoRefreshTimer) clearInterval(autoRefreshTimer);
            }
        });
    }

    // Clickable Stat Cards
    const cardTotal = document.getElementById("cardTotalRisks");
    if (cardTotal) cardTotal.addEventListener("click", () => switchTab("tab-news"));

    const cardCrawled = document.getElementById("cardCrawledCount");
    if (cardCrawled) cardCrawled.addEventListener("click", () => switchTab("tab-sites"));

    const cardHotspot = document.getElementById("cardHotspot");
    if (cardHotspot) {
        cardHotspot.addEventListener("click", () => {
            const hotProv = document.getElementById("statHotspot").innerText.split(" ")[0];
            if (hotProv && hotProv !== "Chưa") {
                currentProvinceFilter = hotProv;
                const pSelect = document.getElementById("provinceFilter");
                if (pSelect) pSelect.value = hotProv;
            }
            switchTab("tab-news");
        });
    }

    const cardNext = document.getElementById("cardNextScan");
    if (cardNext) {
        cardNext.addEventListener("click", () => {
            showToast("⏰ Lịch trình quét tự động cài đặt cố định lúc 07:00 sáng và 17:00 chiều hằng ngày", "info");
        });
    }

    // Set default date for scanDateFrom and scanDateTo to Today YYYY-MM-DD
    const todayStr = getLocalTodayISO();
    const scanDateFrom = document.getElementById("scanDateFrom");
    const scanDateTo = document.getElementById("scanDateTo");
    if (scanDateFrom && !scanDateFrom.value) scanDateFrom.value = todayStr;
    if (scanDateTo && !scanDateTo.value) scanDateTo.value = todayStr;

    // Buttons
    const btnScan = document.getElementById("btnRunScan");
    if (btnScan) btnScan.addEventListener("click", triggerManualScan);

    const btnScanDash = document.getElementById("btnRunScanDashboard");
    if (btnScanDash) btnScanDash.addEventListener("click", triggerManualScan);


    const btnExcel = document.getElementById("btnDownloadExcel");

    if (btnExcel) btnExcel.addEventListener("click", downloadExcelReport);

    const btnDocx = document.getElementById("btnDownloadDocx");
    if (btnDocx) btnDocx.addEventListener("click", downloadDocxReport);

    // Forms
    const subForm = document.getElementById("subscriberForm");
    if (subForm) subForm.addEventListener("submit", addSubscriber);

    const siteForm = document.getElementById("addSiteForm");
    if (siteForm) siteForm.addEventListener("submit", addMonitoredSite);
}

async function loadDashboardStats() {
    try {
        const res = await fetch("/api/stats");
        const sitesRes = await fetch("/api/sites");
        if (res.ok) {
            const data = await res.json();
            let siteCount = 9;
            if (sitesRes.ok) {
                const sites = await sitesRes.json();
                siteCount = sites.length;
            }
            document.getElementById("statTotalRisks").innerText = data.total_risks || 0;
            document.getElementById("statCrawledCount").innerText = `${siteCount} Trang báo`;
            document.getElementById("statHotspot").innerText = data.top_province || "Chưa có";
            document.getElementById("statNextScan").innerText = data.next_scan || "07:00 / 17:00";
        }
    } catch (err) {
        console.error("Lỗi khi tải thống kê:", err);
    }
}

async function loadTodayNews() {
    const tbody = document.getElementById("todayNewsBody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 2.5rem; color: #94a3b8; font-weight: 500;"><div class="spinner"></div> Đang kết nối CSDL Supabase và tải tin rủi ro mới nhất...</td></tr>`;

    const startTime = Date.now();
    try {
        let res = await fetch("/api/news?period=today");
        if (!res.ok) return;
        let data = await res.json();
        let items = data.items || [];

        // Nếu hôm nay chưa có tin mới, hiển thị toàn bộ các tin rủi ro mới nhất trong CSDL
        if (items.length === 0) {
            const allRes = await fetch("/api/news");
            if (allRes.ok) {
                const allData = await allRes.json();
                items = allData.items || [];
            }
        }

        const elapsed = Date.now() - startTime;
        if (elapsed < 500) {
            await new Promise(resolve => setTimeout(resolve, 500 - elapsed));
        }

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 2rem; color: #64748b;">Chưa có tin rủi ro nào ghi nhận trong CSDL. Hãy ấn Quét Thủ Công để cào tin!</td></tr>`;
            return;
        }

        tbody.innerHTML = items.map((item, index) => renderTableRowHtml(item, index, "today")).join("");
        window._todayItems = items;
    } catch (err) {
        console.error("Lỗi tải tin hôm nay:", err);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 2rem; color: #ef4444;">❌ Lỗi tải dữ liệu: ${err.message}</td></tr>`;
    }
}



async function loadEarlierNews() {
    const tbody = document.getElementById("earlierNewsBody");
    if (!tbody) return;

    try {
        const res = await fetch("/api/news?period=earlier");
        if (!res.ok) return;
        const data = await res.json();
        const items = data.items || [];

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 2rem; color: #64748b;">Chưa có tin rủi ro nào từ các ngày trước.</td></tr>`;
            return;
        }

        tbody.innerHTML = items.map((item, index) => renderTableRowHtml(item, index, "earlier")).join("");
        window._earlierItems = items;
    } catch (err) {
        console.error("Lỗi tải tin trước đó:", err);
    }
}

async function loadMonitoredSites() {
    const grid = document.getElementById("monitoredSitesGrid");
    if (!grid) return;

    try {
        const res = await fetch("/api/sites");
        if (!res.ok) return;
        const sites = await res.json();

        if (sites.length === 0) {
            grid.innerHTML = `<div style="color: #94a3b8;">Chưa có trang báo nào trong danh sách.</div>`;
            return;
        }

        grid.innerHTML = sites.map(site => `
            <div class="glass-panel" style="padding: 1.1rem; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid rgba(212,175,55,0.2);">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <h4 style="font-size: 0.95rem; font-weight: 700; color: #ffffff;">${escapeHtml(site.name)}</h4>
                        <button onclick="deleteMonitoredSite(${site.id})" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 0.9rem;" title="Xóa trang báo">
                            🗑️
                        </button>
                    </div>
                    <div style="font-size: 0.75rem; color: #f3e5ab; margin-bottom: 0.5rem;">
                        📍 Địa bàn: ${escapeHtml(site.province_hint || "Toàn quốc")}
                    </div>
                    <div style="font-size: 0.75rem; color: #94a3b8; word-break: break-all; margin-bottom: 0.85rem;">
                        🔗 ${escapeHtml(site.url)}
                    </div>
                </div>
                <a href="${escapeHtml(site.url)}" target="_blank" class="btn-glass" style="font-size: 0.75rem; padding: 0.4rem 0.8rem; justify-content: center; text-decoration: none;">
                    🌐 Ghé thăm trang ↗
                </a>
            </div>
        `).join("");

    } catch (err) {
        console.error("Lỗi tải danh sách trang báo:", err);
    }
}

async function addMonitoredSite(e) {
    e.preventDefault();
    const name = document.getElementById("siteName").value.trim();
    const url = document.getElementById("siteUrl").value.trim();
    const province_hint = document.getElementById("siteProvince").value;

    if (!name || !url) return;

    try {
        const res = await fetch("/api/sites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, url, province_hint })
        });

        if (res.ok) {
            showToast("✅ Đã thêm trang báo mục tiêu mới!", "success");
            document.getElementById("addSiteForm").reset();
            loadMonitoredSites();
            loadDashboardStats();
        } else {
            const errData = await res.json();
            showToast(`⚠️ Lỗi: ${errData.detail || "Không thể thêm trang báo"}`, "error");
        }
    } catch (err) {
        showToast(`❌ Lỗi kết nối: ${err.message}`, "error");
    }
}

async function deleteMonitoredSite(siteId) {
    if (!confirm("Bạn có chắc chắn muốn xóa trang báo này khỏi hệ thống giám sát?")) return;

    try {
        const res = await fetch(`/api/sites/${siteId}`, { method: "DELETE" });
        if (res.ok) {
            showToast("🗑️ Đã xóa trang báo khỏi hệ thống", "info");
            loadMonitoredSites();
            loadDashboardStats();
        }
    } catch (err) {
        showToast("❌ Lỗi khi xóa trang báo", "error");
    }
}

async function loadNewsTable() {
    const tbody = document.getElementById("newsTableBody");
    const quickBody = document.getElementById("quickNewsBody");

    if (!tbody) return;

    tbody.innerHTML = `
        <tr>
            <td colspan="5" style="text-align: center; padding: 2rem; color: #94a3b8;">
                <div class="spinner"></div> Đang tải dữ liệu tin tức rủi ro...
            </td>
        </tr>
    `;

    try {
        let params = new URLSearchParams();
        params.append("province", currentProvinceFilter);
        if (currentEntityTypeFilter) params.append("entity_type", currentEntityTypeFilter);
        if (currentDateFrom) params.append("date_from", currentDateFrom);
        if (currentDateTo) params.append("date_to", currentDateTo);
        if (currentSearchQuery) params.append("search", currentSearchQuery);

        const res = await fetch(`/api/news?${params.toString()}`);
        if (!res.ok) throw new Error("Không thể tải tin tức");

        const data = await res.json();
        const items = data.items || [];

        if (items.length === 0) {
            const emptyHtml = `
                <tr>
                    <td colspan="5" style="text-align: center; padding: 3rem; color: #64748b;">
                        🔍 Không tìm thấy tin rủi ro nào phù hợp với khoảng thời gian, khu vực và loại đối tượng đã chọn.
                    </td>
                </tr>
            `;
            tbody.innerHTML = emptyHtml;
            if (quickBody) quickBody.innerHTML = emptyHtml;
            return;
        }

        tbody.innerHTML = items.map((item, index) => renderTableRowHtml(item, index, "all")).join("");

        if (quickBody) {
            quickBody.innerHTML = items.slice(0, 5).map((item, index) => renderTableRowHtml(item, index, "all")).join("");
        }

        window._cachedItems = items;

    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 2rem; color: #ef4444;">
                    ❌ Lỗi khi tải dữ liệu: ${err.message}
                </td>
            </tr>
        `;
    }
}

function renderTableRowHtml(item, index, cacheType) {
    const badgeClass = getBadgeClassByRisk(item.risk_type);
    const entityDisplay = item.entity_name ? escapeHtml(item.entity_name) : '<em style="color: #64748b;">(Chưa xác định tên đối tượng)</em>';
    const typeBadge = item.entity_type === "Doanh nghiệp"
        ? '<span style="font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; background: rgba(6, 182, 212, 0.2); color: #38bdf8; border: 1px solid rgba(6, 182, 212, 0.4); margin-left: 6px;">🏢 Doanh nghiệp</span>'
        : (item.entity_type === "Cá nhân" 
            ? '<span style="font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); margin-left: 6px;">👤 Cá nhân</span>'
            : '');

    return `
        <tr class="clickable-row" onclick="openDetailModal(${index}, '${cacheType}')">
            <td style="font-weight: 700; color: #ffffff; width: 24%;">
                <div style="font-size: 0.95rem; display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
                    ${entityDisplay} ${typeBadge}
                </div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">ID: #${item.id}</div>
            </td>
            <td style="line-height: 1.5; color: #cbd5e1; width: 33%;">
                ${escapeHtml(item.summary)}
            </td>
            <td style="width: 13%;">
                <span class="badge-neon badge-blue">
                    📍 ${escapeHtml(item.province)}
                </span>
            </td>

            <td style="width: 15%;">
                <span class="badge-neon ${badgeClass}">
                    ⚠️ ${escapeHtml(item.risk_type)}
                </span>
            </td>
            <td style="width: 15%; font-size: 0.85rem;" onclick="event.stopPropagation()">
                <div style="color: #94a3b8; margin-bottom: 4px;">📅 ${escapeHtml(item.published_date)}</div>
                <a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener" 
                   style="color: #38bdf8; text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                   Xem bài gốc ↗
                </a>
            </td>
        </tr>
    `;
}

function openDetailModal(itemIndex, cacheType = "all") {
    let items = window._cachedItems || [];
    if (cacheType === "today") items = window._todayItems || [];
    if (cacheType === "earlier") items = window._earlierItems || [];

    const item = items[itemIndex];
    if (!item) return;

    currentModalItem = item;

    document.getElementById("modalProvBadge").innerText = `📍 ${item.province || "Chưa xác định"}`;
    document.getElementById("modalRiskBadge").innerText = `⚠️ ${item.risk_type || "Rủi ro"}`;
    document.getElementById("modalEntity").innerHTML = item.entity_name ? escapeHtml(item.entity_name) : '<em style="color: #94a3b8;">(Bài viết chưa xác định rõ tên đối tượng cụ thể)</em>';
    document.getElementById("modalPubDate").innerText = `📅 Ngày đăng: ${item.published_date || "Hôm nay"}`;
    document.getElementById("modalId").innerText = `ID: #${item.id}`;
    document.getElementById("modalSummary").innerText = item.summary || "";
    
    const srcBtn = document.getElementById("modalSourceBtn");
    if (srcBtn) srcBtn.href = item.source_url || "#";

    document.getElementById("detailModal").classList.add("open");
}

function closeDetailModal() {
    document.getElementById("detailModal").classList.remove("open");
}

function copyModalLink() {
    if (currentModalItem && currentModalItem.source_url) {
        navigator.clipboard.writeText(currentModalItem.source_url);
        showToast("📋 Đã copy link bài gốc vào bộ nhớ tạm!", "success");
    }
}

async function loadAnalytics() {
    try {
        const res = await fetch("/api/analytics");
        if (!res.ok) return;

        const data = await res.json();
        const byProv = data.by_province || {};
        const byCat = data.by_category || {};

        const provContainer = document.getElementById("provinceAnalyticsList");
        if (provContainer) {
            const maxProv = Math.max(...Object.values(byProv), 1);
            provContainer.innerHTML = Object.entries(byProv).map(([prov, count]) => {
                const percent = Math.round((count / maxProv) * 100);
                return `
                    <div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #f1f5f9;">
                            <span>📍 ${prov}</span>
                            <span style="color: #f3e5ab;">${count} vụ việc</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: ${percent}%;"></div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        const catContainer = document.getElementById("categoryAnalyticsList");
        if (catContainer) {
            const maxCat = Math.max(...Object.values(byCat), 1);
            catContainer.innerHTML = Object.entries(byCat).map(([cat, count]) => {
                const percent = Math.round((count / maxCat) * 100);
                return `
                    <div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #f1f5f9;">
                            <span>⚠️ ${cat}</span>
                            <span style="color: #f59e0b;">${count} bài báo</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: ${percent}%; background: linear-gradient(90deg, #f59e0b, #ef4444);"></div>
                        </div>
                    </div>
                `;
            }).join("");
        }

    } catch (err) {
        console.error("Lỗi khi tải analytics:", err);
    }
}

async function loadScanLogs() {
    const tbody = document.getElementById("logsTableBody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #94a3b8;"><div class="spinner"></div> Đang kết nối CSDL và tải nhật ký quét...</td></tr>`;

    try {
        const res = await fetch("/api/logs");
        if (!res.ok) return;

        const logs = await res.json();
        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #64748b;">Chưa có nhật ký quét nào.</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(log => {
            let timeStr = log.scan_time || "";
            let formattedTime = timeStr;
            try {
                if (timeStr) {
                    const isoTime = timeStr.replace(" ", "T");
                    formattedTime = new Date(isoTime).toLocaleString('vi-VN');
                    if (formattedTime === "Invalid Date") formattedTime = timeStr;
                }
            } catch (e) {
                formattedTime = timeStr;
            }

            const crawled = log.total_crawled !== undefined ? log.total_crawled : (log.articles_crawled || 0);
            const filtered = log.pre_filtered_count !== undefined ? log.pre_filtered_count : (log.regex_passed || 0);
            const risks = log.risks_extracted || 0;
            const status = log.status || "SUCCESS";
            const msg = log.message || "";

            return `
                <tr>
                    <td style="font-size: 0.85rem; color: #94a3b8;">${escapeHtml(formattedTime)}</td>
                    <td>${crawled} bài</td>
                    <td>${filtered} bài</td>
                    <td style="font-weight: 700; color: #10b981;">${risks} rủi ro</td>
                    <td>
                        <span class="badge-neon ${status === 'SUCCESS' ? 'badge-green' : 'badge-red'}">
                            ${escapeHtml(status)}
                        </span>
                    </td>
                    <td style="font-size: 0.85rem; color: #cbd5e1;">${escapeHtml(msg)}</td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Lỗi tải scan logs:", err);
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">❌ Lỗi khi tải nhật ký: ${err.message}</td></tr>`;
    }
}


let isScanInProgress = false;

async function triggerManualScan() {
    if (isScanInProgress) {
        console.warn("⚠️ Tiến trình quét đang được thực hiện, bỏ qua lần kích hoạt trùng lặp.");
        return;
    }
    isScanInProgress = true;

    const btn = document.getElementById("btnRunScan") || document.getElementById("btnRunScanDashboard");
    const btnDash = document.getElementById("btnRunScanDashboard");
    
    const originalText = btn ? btn.innerHTML : "⚡ Quét Thủ Công";
    if (btn) { btn.disabled = true; btn.innerHTML = `<div class="spinner"></div> Đang tiến hành cào & quét AI...`; }
    if (btnDash) { btnDash.disabled = true; btnDash.innerHTML = `<div class="spinner"></div> Đang quét...`; }

    const dateFrom = document.getElementById("scanDateFrom")?.value || "";
    const dateTo = document.getElementById("scanDateTo")?.value || "";
    const province = document.getElementById("scanProvince")?.value || "Tất cả";
    const maxArticles = parseInt(document.getElementById("scanMaxArticles")?.value || "50");

    showToast(`🔍 Đang kích hoạt quét tin (${maxArticles} bài/báo, Khu vực: ${province}, Từ: ${dateFrom || 'Hôm nay'}, Đến: ${dateTo || 'Hôm nay'})...`, "info");

    try {
        const res = await fetch("/api/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date_from: dateFrom,
                date_to: dateTo,
                province: province,
                max_articles: maxArticles
            })
        });

        if (res.status === 504 || res.status === 502) {
            throw new Error("Quá thời gian chờ của Vercel Serverless (Timeout). Vui lòng hạ số bài/báo xuống 15-20 bài hoặc chờ Lịch quét tự động 07:00 & 17:00!");
        }

        const data = await res.json();


        if (res.ok && (data.status === "PROCESSING" || data.status === "SUCCESS")) {
            showToast(`⏳ ${data.message || 'Đã khởi chạy tiến trình quét ngầm thành công!'}`, "info");
            
            // Đồng bộ bộ lọc giao diện với tham số vừa quét thủ công
            if (dateFrom) currentDateFrom = dateFrom;
            if (dateTo) currentDateTo = dateTo;
            if (province) currentProvinceFilter = province;

            const pSelect = document.getElementById("provinceFilter");
            if (pSelect) pSelect.value = province;

            const startDateInput = document.getElementById("startDate");
            if (startDateInput) startDateInput.value = dateFrom;

            const endDateInput = document.getElementById("endDate");
            if (endDateInput) endDateInput.value = dateTo;

            loadDashboardStats();
            loadNewsTable();
            loadTodayNews();
            loadAnalytics();
            loadScanLogs();
            switchTab("tab-today");

            // Tự động poll làm mới dữ liệu liên tục trong 90s
            let pollCount = 0;
            const pollTimer = setInterval(() => {
                pollCount++;
                loadDashboardStats();
                loadNewsTable();
                loadTodayNews();
                loadScanLogs();
                if (pollCount >= 30) {
                    clearInterval(pollTimer);
                    showToast("✅ Đã tự động cập nhật xong dữ liệu từ đợt quét ngầm!", "success");
                }
            }, 3000);

        } else {
            showToast(`⚠️ Quét thất bại: ${data.message || data.error}`, "error");
        }

    } catch (err) {
        showToast(`❌ Lỗi hệ thống: ${err.message}`, "error");
    } finally {
        isScanInProgress = false;
        if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
        if (btnDash) { btnDash.disabled = false; btnDash.innerHTML = "⚡ Quét Thủ Công"; }
    }
}
window.triggerManualScan = triggerManualScan;




function downloadExcelReport() {
    let params = new URLSearchParams();
    params.append("province", currentProvinceFilter);
    if (currentDateFrom) params.append("date_from", currentDateFrom);
    if (currentDateTo) params.append("date_to", currentDateTo);

    window.location.href = `/api/reports/download/excel?${params.toString()}`;
}

function downloadDocxReport() {
    const today = currentDateTo || new Date().toISOString().split('T')[0];
    window.location.href = `/api/reports/download/${today}`;
}

async function loadSubscribers() {
    const container = document.getElementById("subscribersList");
    if (!container) return;

    try {
        const res = await fetch("/api/settings/email");
        if (!res.ok) return;

        const subs = await res.json();
        if (subs.length === 0) {
            container.innerHTML = `<div style="color: #64748b; font-size: 0.85rem;">Chưa có email đăng ký nhận cảnh báo nào.</div>`;
            return;
        }

        container.innerHTML = subs.map(sub => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.8rem; background: rgba(255,255,255,0.03); border-radius: 0.5rem; margin-bottom: 0.5rem; border: 1px solid rgba(255,255,255,0.08);">
                <div>
                    <div style="font-weight: 600; font-size: 0.85rem; color: #f1f5f9;">${escapeHtml(sub.name)} (${escapeHtml(sub.email)})</div>
                    <div style="font-size: 0.75rem; color: #38bdf8;">Khu vực nhận: ${escapeHtml(sub.target_province)}</div>
                </div>
                <button onclick="deleteSubscriber(${sub.id})" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 1rem;" title="Xóa người nhận">
                    🗑️
                </button>
            </div>
        `).join("");
    } catch (err) {
        console.error("Lỗi tải subscriber:", err);
    }
}

async function addSubscriber(e) {
    e.preventDefault();
    const name = document.getElementById("subName").value.trim();
    const email = document.getElementById("subEmail").value.trim();
    const province = document.getElementById("subProvince").value;

    if (!name || !email) return;

    try {
        const res = await fetch("/api/settings/email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, target_province: province })
        });

        if (res.ok) {
            showToast("✅ Thêm email nhận cảnh báo thành công!", "success");
            document.getElementById("subscriberForm").reset();
            loadSubscribers();
        } else {
            const errData = await res.json();
            showToast(`⚠️ Lỗi: ${errData.detail || "Không thể thêm email"}`, "error");
        }
    } catch (err) {
        showToast(`❌ Lỗi kết nối: ${err.message}`, "error");
    }
}

async function deleteSubscriber(id) {
    if (!confirm("Bạn có chắc chắn muốn xóa email này khỏi danh sách nhận tin?")) return;

    try {
        const res = await fetch(`/api/settings/email/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Đã xóa email subscriber", "info");
            loadSubscribers();
        }
    } catch (err) {
        showToast("Lỗi khi xóa subscriber", "error");
    }
}

function getBadgeClassByRisk(riskType) {
    const t = (riskType || "").toLowerCase();
    if (t.includes("bắt") || t.includes("khởi tố") || t.includes("lừa đảo") || t.includes("hình sự")) return "badge-red";
    if (t.includes("thuế") || t.includes("phạt") || t.includes("giấy phép")) return "badge-yellow";
    if (t.includes("môi trường") || t.includes("tai nạn")) return "badge-purple";
    return "badge-blue";
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = "glass-panel";
    toast.style.cssText = `
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        padding: 1rem 1.5rem;
        z-index: 9999;
        font-weight: 600;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-left: 4px solid ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#d4af37'};
        animation: slideUp 0.3s ease;
    `;
    toast.innerHTML = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.5s ease";
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}
