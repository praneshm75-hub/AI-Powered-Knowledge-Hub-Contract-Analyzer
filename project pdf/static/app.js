/* ==========================================================================
   ClauseMind AI - Frontend Reactive Logic & SSE RAG Streaming Engine
   ========================================================================== */

let activeDocId = "doc_msa_001";
let activeDocData = null;
let userProfile = null;
let currentTab = "reader";
let rateLimitTimerInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    initApp();

    // Event Listeners
    document.getElementById("btnSendChat").addEventListener("click", sendChatMessage);
    document.getElementById("chatInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    document.getElementById("btnRefreshDocs").addEventListener("click", fetchDocuments);
    document.getElementById("oauthSelect").addEventListener("change", (e) => switchOAuthProvider(e.target.value));
    document.getElementById("btnSimulateRateLimit").addEventListener("click", triggerRateLimitTest);
    
    // Modal Listeners
    document.getElementById("btnOpenUpgrade").addEventListener("click", () => openModal("modalUpgrade"));
    document.getElementById("btnOpenWebhooks").addEventListener("click", () => {
        openModal("modalWebhooks");
        fetchWebhookLogs();
    });
    document.getElementById("btnOpenVectorViz").addEventListener("click", () => {
        switchMainTab("vector");
        loadVectorSpaceViz();
    });
    document.getElementById("btnCompletePayment").addEventListener("click", completePaymentCheckout);
    document.getElementById("btnSimulateCustomWebhook").addEventListener("click", dispatchCustomWebhook);
    document.getElementById("fileInput").addEventListener("change", handleFileUpload);
});

async function initApp() {
    await fetchUserProfile();
    await fetchDocuments();
}

async function fetchUserProfile() {
    try {
        const res = await fetch("/api/user/profile");
        userProfile = await res.json();
        updateProfileUI(userProfile);
    } catch (e) {
        console.error("Error fetching user profile:", e);
    }
}

function updateProfileUI(profile) {
    document.getElementById("userName").textContent = profile.name;
    document.getElementById("userProvider").textContent = profile.provider;
    document.getElementById("userTierName").textContent = profile.tier_details.name;
    document.getElementById("userAvatar").src = profile.avatar;

    // Quotas
    const qUsed = profile.queries_today;
    const qLimit = profile.tier_details.query_daily_limit;
    const qPercent = Math.min(100, Math.round((qUsed / qLimit) * 100));
    document.getElementById("queryQuotaFill").style.width = `${qPercent}%`;
    document.getElementById("queryQuotaText").textContent = `${qUsed} / ${qLimit} queries`;

    const uUsed = profile.uploads_used;
    const uLimit = profile.tier_details.upload_limit;
    const uPercent = Math.min(100, Math.round((uUsed / uLimit) * 100));
    document.getElementById("uploadQuotaFill").style.width = `${uPercent}%`;
    document.getElementById("uploadQuotaText").textContent = `${uUsed} / ${uLimit} PDFs`;

    const remaining = Math.max(0, qLimit - qUsed);
    document.getElementById("chatQueryRemaining").textContent = `${remaining} Queries left today (${profile.tier})`;
}

async function switchOAuthProvider(providerName) {
    try {
        const res = await fetch("/api/user/auth", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: providerName })
        });
        const data = await res.json();
        userProfile = data.profile;
        updateProfileUI(userProfile);
        showNotification(`Switched identity to ${providerName}`);
    } catch (e) {
        console.error("Auth switch failed:", e);
    }
}

async function fetchDocuments() {
    try {
        const res = await fetch("/api/documents");
        const data = await res.json();
        renderDocumentList(data.documents || []);
        if (data.documents && data.documents.length > 0) {
            selectDocument(data.documents[0].id);
        }
    } catch (e) {
        console.error("Error fetching documents:", e);
    }
}

function renderDocumentList(documents) {
    const container = document.getElementById("docListContainer");
    container.innerHTML = "";

    documents.forEach(doc => {
        const card = document.createElement("div");
        card.className = `doc-card ${doc.id === activeDocId ? 'active' : ''}`;
        card.onclick = () => selectDocument(doc.id);

        card.innerHTML = `
            <div class="doc-card-title">${escapeHtml(doc.title)}</div>
            <div class="doc-card-sub">
                <span><i class="fa-solid fa-file"></i> ${doc.pages} pgs</span>
                <span>${doc.category}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

async function selectDocument(docId) {
    activeDocId = docId;

    // Update active highlight in sidebar
    document.querySelectorAll(".doc-card").forEach(c => c.classList.remove("active"));
    
    try {
        const res = await fetch(`/api/documents/${docId}`);
        const data = await res.json();
        activeDocData = data.document;

        document.getElementById("activeDocTitle").textContent = activeDocData.title;
        document.getElementById("docMetaCategory").innerHTML = `<i class="fa-solid fa-tag"></i> ${activeDocData.category}`;
        document.getElementById("docMetaPages").innerHTML = `<i class="fa-solid fa-file-lines"></i> ${activeDocData.pages} Pages`;
        document.getElementById("docMetaSize").innerHTML = `<i class="fa-solid fa-hard-drive"></i> ${activeDocData.file_size}`;

        renderDocumentReader(activeDocData);
        loadRiskRadar(docId);
    } catch (e) {
        console.error("Error selecting document:", e);
    }
}

function renderDocumentReader(doc) {
    const container = document.getElementById("docViewerText");
    container.innerHTML = "";

    const clauses = doc.clauses || [];
    if (clauses.length === 0) {
        container.innerHTML = `<div class="clause-box"><p>${escapeHtml(doc.raw_text)}</p></div>`;
        return;
    }

    clauses.forEach((c, idx) => {
        const box = document.createElement("div");
        box.className = "clause-box";
        box.id = `clause-node-${c.id}`;

        let riskBadge = '';
        if (c.risk_level === 'HIGH') {
            riskBadge = `<span class="badge badge-risk-high"><i class="fa-solid fa-circle-exclamation"></i> HIGH RISK</span>`;
        } else if (c.risk_level === 'MEDIUM') {
            riskBadge = `<span class="badge badge-risk-med"><i class="fa-solid fa-triangle-exclamation"></i> MEDIUM RISK</span>`;
        } else {
            riskBadge = `<span class="badge badge-risk-low"><i class="fa-solid fa-circle-check"></i> LOW RISK</span>`;
        }

        box.innerHTML = `
            <div class="clause-header">
                <h4>${escapeHtml(c.title || `Clause ${idx + 1}`)}</h4>
                <div>
                    <span class="text-muted" style="font-size:11px; margin-right:8px;">Page ${c.page || 1}</span>
                    ${riskBadge}
                </div>
            </div>
            <p style="color: #e5e7eb;">${escapeHtml(c.text)}</p>
            ${c.analysis ? `<div class="rec-box mt-2"><strong>Risk Note:</strong> ${escapeHtml(c.analysis)}</div>` : ''}
        `;
        container.appendChild(box);
    });
}

async function loadRiskRadar(docId) {
    try {
        const res = await fetch("/api/analyze-contract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ document_id: docId })
        });
        const data = await res.json();

        document.getElementById("riskScoreNum").textContent = data.risk_score;
        document.getElementById("riskScoreNum").style.color = data.badge_color === 'red' ? '#ef4444' : (data.badge_color === 'amber' ? '#f59e0b' : '#10b981');
        document.getElementById("riskSummaryTitle").textContent = `Audit: ${data.risk_badge}`;
        document.getElementById("riskSummaryDesc").textContent = data.executive_summary;

        document.getElementById("activeRiskBadge").className = `badge badge-risk-${data.badge_color === 'red' ? 'high' : (data.badge_color === 'amber' ? 'med' : 'low')}`;
        document.getElementById("activeRiskBadge").innerHTML = `<i class="fa-solid fa-shield-halved"></i> ${data.risk_badge}`;

        document.getElementById("cntHighRisk").textContent = `${data.high_risk_count} High Risk`;
        document.getElementById("cntMedRisk").textContent = `${data.medium_risk_count} Medium Risk`;
        document.getElementById("cntLowRisk").textContent = `${data.low_risk_count} Low Risk`;

        document.getElementById("riskCountBadge").textContent = `${data.high_risk_count} High Risk`;

        // Render Clause Analysis Cards
        const container = document.getElementById("clauseAnalysisContainer");
        container.innerHTML = "";

        (data.clauses || []).forEach(c => {
            const card = document.createElement("div");
            card.className = "clause-analysis-card";
            
            let badgeHtml = c.risk_level === 'HIGH' ? `<span class="badge badge-risk-high">HIGH RISK</span>` :
                            (c.risk_level === 'MEDIUM' ? `<span class="badge badge-risk-med">MEDIUM RISK</span>` : `<span class="badge badge-risk-low">LOW RISK</span>`);

            card.innerHTML = `
                <div class="clause-header">
                    <h4>${escapeHtml(c.title)}</h4>
                    ${badgeHtml}
                </div>
                <p class="text-muted" style="font-size:12px; margin-bottom:8px;">${escapeHtml(c.text)}</p>
                <div class="rec-box">
                    <strong class="text-indigo"><i class="fa-solid fa-lightbulb"></i> Recommendation:</strong> ${escapeHtml(c.recommendation)}
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading risk radar:", e);
    }
}

async function loadVectorSpaceViz() {
    try {
        const res = await fetch("/api/vector/visualizer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ document_id: activeDocId, query: "liability cap auto-renewal" })
        });
        const data = await res.json();
        const container = document.getElementById("vectorVizContent");
        container.innerHTML = `
            <div style="background: rgba(99,102,241,0.1); border: 1px solid var(--color-indigo); padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                <strong>Query:</strong> "${escapeHtml(data.query)}" | <strong>Index Type:</strong> ${data.index_type} | <strong>Metric:</strong> ${data.metric}
            </div>
        `;

        (data.matches || []).forEach((m, idx) => {
            const card = document.createElement("div");
            card.className = "vector-match-card";
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="text-indigo">Rank #${idx + 1} - Chunk ID: ${m.chunk.id}</span>
                    <span class="text-emerald">Match Score: ${m.similarity_percent} (Distance: ${m.pgvector_distance})</span>
                </div>
                <div class="vector-metric-bar">
                    <div style="width: ${m.similarity_percent}; height:100%; background: var(--color-indigo);"></div>
                </div>
                <p class="text-muted" style="font-size:11px;">"${escapeHtml(m.chunk.text)}..."</p>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading vector space:", e);
    }
}

async function sendChatMessage() {
    const input = document.getElementById("chatInput");
    const query = input.value.trim();
    if (!query) return;

    input.value = "";
    appendUserMessage(query);

    // Create AI response message container for streaming
    const aiMsgObj = appendAIMessagePlaceholder();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ document_id: activeDocId, query: query })
        });

        if (response.status === 429) {
            const errData = await response.json();
            aiMsgObj.contentEl.innerHTML = `<span class="text-rose"><i class="fa-solid fa-circle-xmark"></i> ${escapeHtml(errData.message || "Quota Limit Exceeded")}</span>`;
            showRateLimitModal(errData.retry_after_seconds || 45);
            return;
        }

        if (!response.ok) {
            let errorMsg = `Server Error (${response.status})`;
            try {
                const errData = await response.json();
                if (errData.message) errorMsg = errData.message;
            } catch (ignore) {}
            aiMsgObj.contentEl.innerHTML = `<span class="text-rose"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(errorMsg)}</span>`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let fullText = "";
        let pendingBuffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            pendingBuffer += decoder.decode(value, { stream: true });
            const lines = pendingBuffer.split("\n");
            pendingBuffer = lines.pop(); // Keep last incomplete line in buffer

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith("data: ")) {
                    try {
                        const jsonStr = trimmed.replace("data: ", "").trim();
                        if (!jsonStr) continue;
                        const data = JSON.parse(jsonStr);

                        fullText += data.token;
                        aiMsgObj.contentEl.innerHTML = formatMarkdown(fullText);

                        if (data.citations && data.citations.length > 0) {
                            renderCitations(aiMsgObj.contentEl, data.citations);
                        }

                        // Auto-scroll chat
                        const chatContainer = document.getElementById("chatMessages");
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    } catch (err) {
                        // ignore malformed JSON chunk
                    }
                }
            }
        }

        // Handle any remaining line in buffer
        if (pendingBuffer.trim().startsWith("data: ")) {
            try {
                const data = JSON.parse(pendingBuffer.trim().replace("data: ", ""));
                fullText += data.token;
                aiMsgObj.contentEl.innerHTML = formatMarkdown(fullText);
                if (data.citations && data.citations.length > 0) {
                    renderCitations(aiMsgObj.contentEl, data.citations);
                }
            } catch (err) {}
        }

        // Refresh user quota UI after query
        fetchUserProfile();
    } catch (e) {
        console.error("Error in chat streaming:", e);
        aiMsgObj.contentEl.innerHTML = `<span class="text-rose"><i class="fa-solid fa-plug-circle-xmark"></i> Network error connecting to backend stream: ${escapeHtml(e.message || "Connection interrupted")}</span>`;
    }
}

function sendQuickPrompt(promptText) {
    document.getElementById("chatInput").value = promptText;
    sendChatMessage();
}

function appendUserMessage(text) {
    const container = document.getElementById("chatMessages");
    const msg = document.createElement("div");
    msg.className = "message msg-user";
    msg.innerHTML = `
        <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
        <div class="msg-content">${escapeHtml(text)}</div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function appendAIMessagePlaceholder() {
    const container = document.getElementById("chatMessages");
    const msg = document.createElement("div");
    msg.className = "message msg-ai";
    const contentEl = document.createElement("div");
    contentEl.className = "msg-content";
    contentEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-indigo"></i> Querying vector database...`;

    msg.innerHTML = `<div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>`;
    msg.appendChild(contentEl);
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
    return { msgEl: msg, contentEl: contentEl };
}

function renderCitations(containerEl, citations) {
    const citBox = document.createElement("div");
    citBox.className = "citations-wrapper mt-2";
    citBox.innerHTML = `<strong class="text-muted" style="font-size:10px; display:block;">Source Vector Citations:</strong>`;

    citations.forEach(c => {
        const pill = document.createElement("span");
        pill.className = "citation-pill";
        pill.innerHTML = `<i class="fa-solid fa-bookmark"></i> Page ${c.page} (${c.similarity})`;
        pill.onclick = () => scrollToClauseInReader(c.chunk_id);
        citBox.appendChild(pill);
    });

    containerEl.appendChild(citBox);
}

function scrollToClauseInReader(chunkId) {
    switchMainTab('reader');

    // Try finding exact node or pulse all clause boxes
    const node = document.getElementById(`clause-node-${chunkId}`) || document.querySelector(".clause-box");
    if (node) {
        node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        node.classList.add("highlight-pulse");
        setTimeout(() => node.classList.remove("highlight-pulse"), 3000);
    }
}

function switchMainTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    if (tabName === 'reader') {
        document.getElementById("tabDocReader").classList.add("active");
        document.getElementById("viewDocReader").classList.add("active");
    } else if (tabName === 'radar') {
        document.getElementById("tabRiskRadar").classList.add("active");
        document.getElementById("viewRiskRadar").classList.add("active");
    } else if (tabName === 'vector') {
        document.getElementById("tabVectorViz").classList.add("active");
        document.getElementById("viewVectorViz").classList.add("active");
    }
}

async function triggerRateLimitTest() {
    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "X-Simulate-Limit": "true"
            },
            body: JSON.stringify({ simulate_rate_limit: true })
        });
        
        if (res.status === 429) {
            const data = await res.json();
            showRateLimitModal(data.retry_after_seconds || 45);
        }
    } catch (e) {
        console.error("Rate limit test failed:", e);
    }
}

function showRateLimitModal(seconds) {
    openModal("modalRateLimit");
    let remaining = seconds;
    const timerEl = document.getElementById("rateLimitTimer");

    if (rateLimitTimerInterval) clearInterval(rateLimitTimerInterval);
    timerEl.textContent = `00:${remaining < 10 ? '0' : ''}${remaining}`;

    rateLimitTimerInterval = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(rateLimitTimerInterval);
            timerEl.textContent = "00:00 - Quota Reset!";
        } else {
            timerEl.textContent = `00:${remaining < 10 ? '0' : ''}${remaining}`;
        }
    }, 1000);
}

function selectTierForCheckout(tierName) {
    document.getElementById("cardTierPro").classList.remove("featured");
    document.getElementById("cardTierEnterprise").classList.remove("featured");

    if (tierName === 'PRO') {
        document.getElementById("cardTierPro").classList.add("featured");
    } else {
        document.getElementById("cardTierEnterprise").classList.add("featured");
    }

    showNotification(`Selected ${tierName} Tier for Checkout`);
}

async function completePaymentCheckout() {
    const cardLast4 = document.getElementById("cardNumber").value.slice(-4) || "4242";
    try {
        const res = await fetch("/api/subscription/upgrade", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tier: "PRO", card_last4: cardLast4 })
        });
        const data = await res.json();
        
        closeModal("modalUpgrade");
        userProfile = data.profile;
        updateProfileUI(userProfile);
        showNotification(`🎉 Payment Successful! Upgraded to Pro Tier.`);
    } catch (e) {
        console.error("Checkout failed:", e);
    }
}

async function fetchWebhookLogs() {
    try {
        const res = await fetch("/api/webhooks/logs");
        const data = await res.json();
        const container = document.getElementById("webhookTerminal");
        container.innerHTML = "";

        (data.logs || []).forEach(log => {
            const entry = document.createElement("div");
            entry.style.marginBottom = "14px";
            entry.innerHTML = `
                <div><span style="color:#10b981;">[${new Date(log.timestamp * 1000).toLocaleTimeString()}]</span> <span style="color:#f59e0b;">EVENT: ${log.type}</span> (${log.id})</div>
                <div style="color:#64748b;">Signature: ${log.signature}</div>
                <pre style="color:#38bdf8; background:rgba(255,255,255,0.02); padding:6px; border-radius:4px;">${JSON.stringify(log.payload, null, 2)}</pre>
            `;
            container.appendChild(entry);
        });
    } catch (e) {
        console.error("Error fetching webhooks:", e);
    }
}

async function dispatchCustomWebhook() {
    try {
        await fetch("/api/webhooks/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                event_type: "invoice.payment_succeeded",
                payload: { invoice_id: "in_99812", amount_paid: 2900, status: "paid" }
            })
        });
        fetchWebhookLogs();
        showNotification("Dispatched Stripe Webhook Event!");
    } catch (e) {
        console.error("Webhook dispatch error:", e);
    }
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
        const text = evt.target.result;
        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: file.name,
                    category: "Custom Upload",
                    raw_text: text
                })
            });
            const data = await res.json();
            showNotification(`Uploaded ${file.name} successfully!`);
            fetchDocuments();
            selectDocument(data.document.id);
        } catch (err) {
            console.error("Upload error:", err);
        }
    };
    reader.readAsText(file);
}

function openModal(id) {
    document.getElementById(id).classList.add("active");
}

function closeModal(id) {
    document.getElementById(id).classList.remove("active");
}

function showNotification(msg) {
    const toast = document.createElement("div");
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.background = "#6366f1";
    toast.style.color = "#fff";
    toast.style.padding = "10px 18px";
    toast.style.borderRadius = "8px";
    toast.style.zIndex = "9999";
    toast.style.boxShadow = "0 10px 25px rgba(0,0,0,0.5)";
    toast.style.fontSize = "12px";
    toast.style.fontWeight = "600";
    toast.textContent = msg;

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
