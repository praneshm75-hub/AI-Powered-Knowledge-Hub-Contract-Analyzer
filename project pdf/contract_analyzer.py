import re
from typing import List, Dict, Any

class ContractAnalyzer:
    """
    Analyzes legal contracts and documents for high-risk clauses, uncapped liabilities,
    broad indemnifications, auto-renewal traps, and financial covenants.
    """

    RISK_PATTERNS = [
        {
            "category": "Liability Cap",
            "regex": r"(unlimited|uncapped|not subject to|exceeding|gross negligence|data breach)",
            "risk": "HIGH",
            "title": "Uncapped Liability Exposure",
            "description": "Liability is unlimited or excludes caps for data breaches/gross negligence.",
            "recommendation": "Negotiate a mutual liability cap equal to 1x-3x Annual Contract Value (ACV)."
        },
        {
            "category": "Indemnification",
            "regex": r"(indemnify|hold harmless|defend against|regardless of fault)",
            "risk": "HIGH",
            "title": "Broad Unilateral Indemnification",
            "description": "Requires client to indemnify provider even if provider is negligent.",
            "recommendation": "Add mutual indemnification and limit scope to direct third-party IP claims."
        },
        {
            "category": "Fee Escalation",
            "regex": r"(increase|escalat|without prior notice|unilateral|fee adjustment)",
            "risk": "MEDIUM",
            "title": "Uncapped Fee Escalation",
            "description": "Subscription prices can rise up to 12% without prior advance notice.",
            "recommendation": "Cap annual price increases at CPI or maximum 3%-5% with 60-day advance notice."
        },
        {
            "category": "Auto-Renewal",
            "regex": r"(automatically renews|auto-renew|90 days|successive)",
            "risk": "MEDIUM",
            "title": "Auto-Renewal & 90-Day Lock-in Window",
            "description": "Strict 90-day non-renewal window locks client into full 12-month extension.",
            "recommendation": "Set calendar reminders 120 days prior to expiry or reduce window to 30 days."
        },
        {
            "category": "Debt Covenant",
            "regex": r"(net debt|ebitda|ratio|covenant|acceleration)",
            "risk": "HIGH",
            "title": "Tight Leverage Ratio Covenant",
            "description": "Net Debt / EBITDA ratio of 3.05x leaves minimal margin before 3.2x covenant breach.",
            "recommendation": "Monitor Q1 debt levels closely to avoid debt acceleration triggers."
        }
    ]

    def analyze_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        clauses = doc.get("clauses", [])
        raw_text = doc.get("raw_text", "")
        
        analyzed_clauses = []
        high_risk_count = 0
        med_risk_count = 0
        low_risk_count = 0

        for c in clauses:
            c_text = c.get("text", "")
            matched_risk = "LOW"
            rec = "Standard clause with minimal risk exposure."
            category = c.get("category", "General")
            flagged_issue = None

            for pattern in self.RISK_PATTERNS:
                if re.search(pattern["regex"], c_text, re.IGNORECASE):
                    matched_risk = pattern["risk"]
                    rec = pattern["recommendation"]
                    flagged_issue = pattern["title"]
                    category = pattern["category"]
                    break

            if matched_risk == "HIGH":
                high_risk_count += 1
            elif matched_risk == "MEDIUM":
                med_risk_count += 1
            else:
                low_risk_count += 1

            analyzed_clauses.append({
                "id": c.get("id"),
                "title": c.get("title"),
                "category": category,
                "risk_level": matched_risk,
                "page": c.get("page", 1),
                "text": c_text,
                "analysis": c.get("analysis", ""),
                "recommendation": rec,
                "flagged_issue": flagged_issue
            })

        # Overall document risk score (0 - 100)
        overall_score = max(10, 100 - (high_risk_count * 25 + med_risk_count * 10))
        if high_risk_count >= 2:
            risk_badge = "CRITICAL RISK"
            badge_color = "red"
        elif high_risk_count == 1 or med_risk_count >= 2:
            risk_badge = "MODERATE RISK"
            badge_color = "amber"
        else:
            risk_badge = "LOW RISK"
            badge_color = "emerald"

        return {
            "document_id": doc.get("id"),
            "document_title": doc.get("title"),
            "risk_score": overall_score,
            "risk_badge": risk_badge,
            "badge_color": badge_color,
            "high_risk_count": high_risk_count,
            "medium_risk_count": med_risk_count,
            "low_risk_count": low_risk_count,
            "clauses": analyzed_clauses,
            "executive_summary": (
                f"Analyzed {len(analyzed_clauses)} clauses in '{doc.get('title')}'. Identified {high_risk_count} High Risk "
                f"and {med_risk_count} Medium Risk contractual exposures. Immediate legal review recommended for Liability and Indemnification terms."
            )
        }
