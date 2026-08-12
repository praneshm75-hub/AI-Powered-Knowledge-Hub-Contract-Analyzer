# ClauseMind AI - AI-Powered Knowledge Hub & Contract Analyzer

![ClauseMind AI Banner](https://img.shields.io/badge/RAG-Vector--Search-6366f1?style=for-the-badge&logo=ai)
![Python 3.10](https://img.shields.io/badge/Python-3.10-10b981?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)

**ClauseMind AI** is an AI-powered Knowledge Hub & Contract Analyzer web application. Users can upload heavy PDFs (legal contracts, research papers, financial reports) and chat with them using vector retrieval (RAG). Features automated clause risk analysis, subscription tier paywalls, rate-limiting counters, and real-time Stripe payment webhook streams.

---

## 🌟 Key Features

- **Document Hub & PDF Parser**: Pre-loaded with Master Services Agreements, Academic RAG Research Papers, and Financial Audit Disclosures. Supports drag-and-drop custom PDF/text uploads.
- **RAG Vector Search Engine**: High-density TF-IDF + Cosine Distance (`1 - cos(theta)`) vector indexing (`pgvector` simulation) with top-K similarity matching.
- **Token-by-Token SSE Streaming**: Real-time word-by-word streaming responses with source citations (`[Page 4 - 96.4% Match]`) that scroll to and highlight exact clauses.
- **Contract Clause Risk Radar**: Automated detection of uncapped liabilities, broad indemnifications, fee escalations, auto-renewal traps, and financial covenants.
- **Subscription Tiers & Rate Limiting**: Free Tier (50 queries/day), Pro Tier ($29/mo), and Enterprise Tier ($199/mo) with interactive Stripe checkout and HTTP 429 paywall modals.
- **Webhook Inspector & OAuth Switcher**: Real-time Stripe webhook log terminal (`checkout.session.completed`, `customer.subscription.updated`) with HMAC signatures and OAuth provider simulation (Google, GitHub, Enterprise SSO).

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ (No external pip/npm packages required!)

### Running the Server
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/clausemind-ai.git
cd clausemind-ai

# Start the application server
python app.py 8000
```

Open your browser at **`http://localhost:8000`**

---

## 📁 Repository Structure

```
├── app.py                 # Main Python Web Server & API Router
├── rag_engine.py          # Vector Embeddings, Cosine Search & Token Streaming
├── contract_analyzer.py   # Clause Risk Audit Rules Engine
├── subscription.py        # Subscription Tiers & Stripe Webhook Dispatcher
├── rate_limiter.py        # HTTP 429 Rate Limiter Middleware
├── .gitignore             # Git Ignore Rules
├── static/
│   ├── index.html         # Glassmorphic Single-Page Application UI
│   ├── styles.css         # CSS Dark Mode Styling System
│   └── app.js             # Reactive Frontend Logic & Streaming Reader
└── data/
    └── samples/           # Pre-loaded Legal, Research, and Financial PDFs/Text
```

---

## 📄 License
MIT License
