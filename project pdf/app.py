import os
import sys
import json
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

# Local imports
from rag_engine import RAGEngine
from contract_analyzer import ContractAnalyzer
from subscription import SubscriptionManager
from rate_limiter import RateLimiter

# Initialize global engines & state
rag_engine = RAGEngine()
contract_analyzer = ContractAnalyzer()
sub_manager = SubscriptionManager()
rate_limiter = RateLimiter(requests_per_minute=12)

# Load sample documents from data/samples
DOCUMENTS_DB: Dict[str, Dict[str, Any]] = {}

def load_sample_documents():
    samples_dir = os.path.join(os.path.dirname(__file__), "data", "samples")
    if os.path.exists(samples_dir):
        for filename in os.listdir(samples_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(samples_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        doc_data = json.load(f)
                        doc_id = doc_data["id"]
                        
                        # Process chunks for vector search
                        raw_text = doc_data.get("raw_text", "")
                        chunks = rag_engine.chunk_document(raw_text)
                        doc_data["chunks"] = chunks
                        
                        DOCUMENTS_DB[doc_id] = doc_data
                except Exception as e:
                    print(f"Error loading sample document {filename}: {e}")

load_sample_documents()

class AppRequestHandler(BaseHTTPRequestHandler):

    def _send_json(self, data: Any, status_code: int = 200, headers: dict = None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Simulate-Limit")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Serve static assets
        if path == "/" or path == "/index.html":
            static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
            return self._send_file(static_file, "text/html; charset=utf-8")
        elif path.startswith("/static/") or path in ["/styles.css", "/app.js"]:
            filename = os.path.basename(path)
            static_file = os.path.join(os.path.dirname(__file__), "static", filename)
            mime = "text/css" if filename.endswith(".css") else ("application/javascript" if filename.endswith(".js") else "text/plain")
            return self._send_file(static_file, mime)

        # API Endpoints
        if path == "/api/documents":
            docs_summary = []
            for d in DOCUMENTS_DB.values():
                docs_summary.append({
                    "id": d["id"],
                    "title": d["title"],
                    "category": d["category"],
                    "upload_date": d["upload_date"],
                    "file_size": d["file_size"],
                    "pages": d["pages"],
                    "summary": d["summary"],
                    "clause_count": len(d.get("clauses", []))
                })
            return self._send_json({"documents": docs_summary})

        elif path.startswith("/api/documents/"):
            doc_id = path.replace("/api/documents/", "")
            if doc_id in DOCUMENTS_DB:
                return self._send_json({"document": DOCUMENTS_DB[doc_id]})
            return self._send_json({"error": "Document not found"}, 404)

        elif path == "/api/user/profile":
            profile = sub_manager.get_profile()
            return self._send_json(profile)

        elif path == "/api/webhooks/logs":
            return self._send_json({"logs": sub_manager.webhook_logs})

        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        raw_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(raw_data)
        except Exception:
            body = {}

        # Handle rate limiting check
        client_ip = self.client_address[0]
        simulate_limit = self.headers.get("X-Simulate-Limit", "false") == "true" or body.get("simulate_rate_limit", False)
        
        if simulate_limit:
            headers = {
                "Retry-After": "45",
                "X-RateLimit-Limit": "5",
                "X-RateLimit-Remaining": "0"
            }
            return self._send_json({
                "error": "Rate Limit Exceeded (HTTP 429)",
                "message": "Daily query limit reached for Free Tier. Upgrade to Pro for unlimited RAG queries.",
                "retry_after_seconds": 45,
                "upgrade_url": "/api/subscription/upgrade"
            }, 429, headers)

        if path == "/api/chat":
            # Check user query limits
            allowed, msg = sub_manager.check_query_allowed()
            if not allowed:
                return self._send_json({
                    "error": "Usage Limit Exceeded",
                    "message": msg,
                    "retry_after_seconds": 3600,
                    "tier": sub_manager.active_user["tier"]
                }, 429)

            doc_id = body.get("document_id", "doc_msa_001")
            query = body.get("query", "What is the liability cap?")
            
            doc = DOCUMENTS_DB.get(doc_id)
            if not doc:
                doc = list(DOCUMENTS_DB.values())[0] if DOCUMENTS_DB else None

            if not doc:
                return self._send_json({"error": "No document selected"}, 400)

            # Perform vector search (pgvector simulation)
            chunks = doc.get("chunks", [])
            top_matches = rag_engine.vector_search(query, chunks, top_k=3)
            
            # Generate streaming tokens
            tokens = rag_engine.generate_rag_response_tokens(query, doc["title"], top_matches)

            # Return SSE stream (Server-Sent Events)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            for t_item in tokens:
                chunk_str = f"data: {json.dumps(t_item)}\n\n"
                try:
                    self.wfile.write(chunk_str.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    break
                time.sleep(0.03) # Simulate realistic word streaming typing delay
            
            self.close_connection = True
            return

        elif path == "/api/analyze-contract":
            doc_id = body.get("document_id", "doc_msa_001")
            doc = DOCUMENTS_DB.get(doc_id)
            if not doc:
                return self._send_json({"error": "Document not found"}, 404)

            analysis_result = contract_analyzer.analyze_document(doc)
            return self._send_json(analysis_result)

        elif path == "/api/user/auth":
            provider = body.get("provider", "Google OAuth")
            updated_profile = sub_manager.switch_oauth_provider(provider)
            return self._send_json({
                "message": f"Authenticated via {provider}",
                "profile": updated_profile
            })

        elif path == "/api/subscription/upgrade":
            target_tier = body.get("tier", "PRO")
            card_last4 = body.get("card_last4", "4242")
            result = sub_manager.upgrade_subscription(target_tier, card_last4)
            return self._send_json(result)

        elif path == "/api/upload":
            title = body.get("title", "Uploaded Legal Contract.pdf")
            category = body.get("category", "Legal Contract")
            raw_text = body.get("raw_text", "")
            
            if not raw_text:
                raw_text = (
                    f"UPLOADED CONTRACT: {title}\n\n"
                    f"Clause 1. Executive Term\nThis uploaded agreement governs software services provided by Apex Vendors to Client.\n\n"
                    f"Clause 5. Limitation of Liability\nLiability is capped at 1x total fees paid in the preceding 6 months.\n\n"
                    f"Clause 9. Governing Law\nThis Agreement shall be governed by Delaware law."
                )

            new_id = f"doc_custom_{int(time.time())}"
            chunks = rag_engine.chunk_document(raw_text)

            new_doc = {
                "id": new_id,
                "title": title,
                "category": category,
                "upload_date": time.strftime("%Y-%m-%d"),
                "file_size": f"{round(len(raw_text) / 1024, 1)} KB",
                "pages": max(1, len(raw_text) // 600),
                "summary": f"User-uploaded {category} with {len(chunks)} parsed vector chunks.",
                "clauses": [
                    {
                        "id": "uc1",
                        "title": "Clause 1. Executive Scope",
                        "category": "Scope",
                        "risk_level": "LOW",
                        "page": 1,
                        "text": raw_text[:200],
                        "analysis": "Parsed from user uploaded document."
                    }
                ],
                "raw_text": raw_text,
                "chunks": chunks
            }

            DOCUMENTS_DB[new_id] = new_doc
            sub_manager.active_user["uploads_used"] += 1

            # Dispatch webhook for upload event
            sub_manager.dispatch_webhook("document.processed", {
                "document_id": new_id,
                "title": title,
                "chunk_count": len(chunks),
                "timestamp": int(time.time())
            })

            return self._send_json({
                "message": "Document uploaded and indexed successfully into pgvector store!",
                "document": new_doc
            })

        elif path == "/api/vector/visualizer":
            doc_id = body.get("document_id", "doc_msa_001")
            query = body.get("query", "liability cap")
            doc = DOCUMENTS_DB.get(doc_id)
            if not doc:
                return self._send_json({"error": "Document not found"}, 404)
            
            top_matches = rag_engine.vector_search(query, doc.get("chunks", []), top_k=5)
            return self._send_json({
                "query": query,
                "document_title": doc["title"],
                "index_type": "HNSW pgvector",
                "metric": "Cosine Distance (<->)",
                "matches": top_matches
            })

        elif path == "/api/webhooks/simulate":
            event_type = body.get("event_type", "customer.subscription.updated")
            custom_payload = body.get("payload", {"status": "active", "tier": "ENTERPRISE"})
            event = sub_manager.dispatch_webhook(event_type, custom_payload)
            return self._send_json({"message": "Webhook dispatched!", "event": event})

        else:
            self.send_error(404, "API Endpoint Not Found")

def run_server(port=8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, AppRequestHandler)
    print(f"[INFO] AI Knowledge Hub & Contract Analyzer running at http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
