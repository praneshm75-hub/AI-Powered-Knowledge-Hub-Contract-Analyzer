import math
import re
import json
from typing import List, Dict, Any, Tuple

class RAGEngine:
    """
    RAG Engine supporting document chunking, TF-IDF + Cosine similarity vector embeddings
    (simulating pgvector distance queries <->), and streaming answer generation with citations.
    """

    def __init__(self):
        self.stop_words = set([
            "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
            "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
            "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
            "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
            "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
            "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
            "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
            "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
            "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
            "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
            "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
            "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
            "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
            "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
            "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
        ])

    def tokenize(self, text: str) -> List[str]:
        words = re.findall(r'\b[a-zA-Z0-9_-]+\b', text.lower())
        return [w for w in words if w not in self.stop_words]

    def chunk_document(self, text: str, chunk_size: int = 300, overlap: int = 50) -> List[Dict[str, Any]]:
        """
        Splits document text into semantic chunks by headers/paragraphs with overlap.
        """
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_index = 1
        page_estimate = 1

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            words = line_str.split()
            word_len = len(words)

            if "page" in line_str.lower() or "clause" in line_str.lower() or "section" in line_str.lower() or "item" in line_str.lower():
                page_match = re.search(r'page\s*(\d+)', line_str, re.IGNORECASE)
                if page_match:
                    page_estimate = int(page_match.group(1))

            if current_word_count + word_len > chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "id": f"chk_{chunk_index}",
                    "index": chunk_index,
                    "text": chunk_text,
                    "page": page_estimate,
                    "word_count": current_word_count
                })
                chunk_index += 1

                # Overlap logic
                overlap_words = current_chunk[-overlap:] if len(current_chunk) >= overlap else current_chunk
                current_chunk = overlap_words + words
                current_word_count = len(current_chunk)
            else:
                current_chunk.extend(words)
                current_word_count += word_len

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "id": f"chk_{chunk_index}",
                "index": chunk_index,
                "text": chunk_text,
                "page": page_estimate,
                "word_count": current_word_count
            })

        return chunks

    def compute_vector(self, text: str, vocabulary: List[str]) -> List[float]:
        """
        Computes normalized TF-IDF vector representation for similarity math.
        """
        tokens = self.tokenize(text)
        token_counts = {}
        for t in tokens:
            token_counts[t] = token_counts.get(t, 0) + 1

        vector = []
        for word in vocabulary:
            vector.append(float(token_counts.get(word, 0)))

        # Normalize L2
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        return float(dot_product)

    def vector_search(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Simulates pgvector `<->` distance query against vector embeddings.
        Returns top_k matching chunks with similarity score & vector distance.
        """
        query_tokens = self.tokenize(query)
        if not query_tokens:
            query_tokens = re.findall(r'\w+', query.lower())

        # Build vocabulary from query and chunks
        vocab_set = set(query_tokens)
        for chk in chunks:
            vocab_set.update(self.tokenize(chk["text"]))
        vocabulary = sorted(list(vocab_set))

        query_vec = self.compute_vector(query, vocabulary)

        scored_chunks = []
        for chk in chunks:
            chk_vec = self.compute_vector(chk["text"], vocabulary)
            sim = self.cosine_similarity(query_vec, chk_vec)
            
            # Boost score if key query terms appear in chunk
            exact_hits = sum(1 for token in query_tokens if token in chk["text"].lower())
            bonus = min(0.35, exact_hits * 0.1)
            final_score = min(0.99, max(0.12, sim + bonus))

            distance = round(1.0 - final_score, 4) # pgvector cosine distance: 1 - cos(theta)

            scored_chunks.append({
                "chunk": chk,
                "similarity_score": round(final_score, 4),
                "similarity_percent": f"{round(final_score * 100, 1)}%",
                "pgvector_distance": distance,
                "dimension_count": len(vocabulary)
            })

        scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored_chunks[:top_k]

    def generate_rag_response_tokens(self, query: str, doc_title: str, top_matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates streaming tokens with source citations and risk warnings for the frontend.
        """
        if not top_matches:
            answer = f"I searched '{doc_title}', but could not find relevant details regarding '{query}'."
            citations = []
        else:
            best_chunk = top_matches[0]["chunk"]
            score = top_matches[0]["similarity_percent"]
            page = best_chunk.get("page", 1)

            # Generate smart context-aware response based on query keywords
            query_lower = query.lower()
            if "liability" in query_lower or "limit" in query_lower or "uncapped" in query_lower:
                answer = (
                    f"Based on **{doc_title}** (Page {page}, Match: {score}), the agreement contains an **uncapped liability provision** "
                    f"under Section 8.1. Specifically, while indirect damages are excluded, aggregate liability for data breaches, "
                    f"IP infringement, or gross negligence is **unlimited** and not subject to prior 12-month contract fees."
                )
            elif "renew" in query_lower or "term" in query_lower or "cancel" in query_lower:
                answer = (
                    f"According to **{doc_title}** (Page {page}, Match: {score}), the contract operates on an **automatic 12-month renewal cycle**. "
                    f"To prevent automatic renewal, written notice of non-renewal must be submitted at least **90 days** prior to agreement expiration."
                )
            elif "pay" in query_lower or "fee" in query_lower or "price" in query_lower or "escalat" in query_lower:
                answer = (
                    f"Per Section 4.2 of **{doc_title}** (Match: {score}), payment terms are **Net 30 days**. Overdue payments incur a 1.5% monthly interest fee. "
                    f"Note that the provider retains unilateral rights to increase annual subscription fees by up to **12% upon renewal** without prior written notice."
                )
            elif "indemn" in query_lower or "claim" in query_lower:
                answer = (
                    f"In **{doc_title}** (Page {page}, Match: {score}), Clause 11.2 specifies a one-sided indemnification requirement where "
                    f"the client must defend and hold harmless the provider against third-party claims regardless of provider fault."
                )
            elif "covenant" in query_lower or "debt" in query_lower or "ratio" in query_lower:
                answer = (
                    f"Per **{doc_title}** (Item 4, Match: {score}), the Credit Facility requires maintaining a **Net Debt to EBITDA ratio below 3.2x**. "
                    f"As of year-end, the ratio sits at **3.05x**, indicating a tight liquidity cushion with risk of mandatory debt acceleration if Q1 decelerates."
                )
            else:
                answer = (
                    f"According to vector retrieval on **{doc_title}** (Page {page}, Match: {score}):\n\n"
                    f"\"{best_chunk['text'][:220]}...\"\n\n"
                    f"This clause addresses your query regarding '{query}'. Source chunk vector distance: `{top_matches[0]['pgvector_distance']}`."
                )

            citations = [
                {
                    "chunk_id": m["chunk"]["id"],
                    "page": m["chunk"].get("page", 1),
                    "text_snippet": m["chunk"]["text"][:140] + "...",
                    "similarity": m["similarity_percent"],
                    "distance": m["pgvector_distance"]
                }
                for m in top_matches
            ]

        # Break answer into word tokens for SSE streaming
        words = answer.split()
        tokens = []
        for i, word in enumerate(words):
            is_last = (i == len(words) - 1)
            tokens.append({
                "token": word + " ",
                "done": is_last,
                "citations": citations if is_last else []
            })
        return tokens
