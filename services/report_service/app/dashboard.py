from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session


def _bucket(rows: list[dict], key: str) -> dict[str, int]:
    return dict(Counter((r.get(key) or "Não informado") for r in rows))


def build_dashboard(db: Session) -> dict:
    sql = text(
        """
        SELECT c.id::text AS id,
               c.raw_text,
               c.status,
               c.channel,
               c.created_at,
               a.blocked,
               a.category,
               a.product,
               a.sentiment,
               a.urgency,
               a.summary,
               a.risk_level,
               a.risk_justification
          FROM complaints.complaints c
     LEFT JOIN complaints.analyses a ON a.complaint_id = c.id
         ORDER BY c.created_at DESC
        """
    )
    rows = [dict(r._mapping) for r in db.execute(sql)]

    total = len(rows)
    blocked = sum(1 for r in rows if r.get("blocked"))
    by_category = _bucket(rows, "category")
    by_product = _bucket(rows, "product")
    by_urgency = _bucket(rows, "urgency")
    by_sentiment = _bucket(rows, "sentiment")
    by_risk = _bucket(rows, "risk_level")

    critical = [
        {
            "id": r["id"],
            "category": r.get("category"),
            "product": r.get("product"),
            "urgency": r.get("urgency"),
            "risk_level": r.get("risk_level"),
            "summary": r.get("summary"),
            "risk_justification": r.get("risk_justification"),
        }
        for r in rows
        if (r.get("urgency") == "Crítica") or (r.get("risk_level") == "Crítico")
    ]

    recommendations = _build_recommendations(by_category, by_risk, critical)

    return {
        "total": total,
        "blocked": blocked,
        "by_category": by_category,
        "by_product": by_product,
        "by_urgency": by_urgency,
        "by_sentiment": by_sentiment,
        "by_risk": by_risk,
        "critical": critical,
        "recommendations": recommendations,
        "rows": rows,
    }


def _build_recommendations(by_category: dict, by_risk: dict, critical: list) -> list[str]:
    recs: list[str] = []
    if critical:
        recs.append(
            f"Escalar imediatamente {len(critical)} reclamação(ões) classificada(s) como crítica(s) para a área de Compliance."
        )
    top_cat = max(by_category.items(), key=lambda x: x[1], default=(None, 0))
    if top_cat[0] and top_cat[1] >= 3:
        recs.append(f"Categoria predominante: {top_cat[0]} ({top_cat[1]} casos). Avaliar causa-raiz e ações preventivas.")
    if by_risk.get("Alto", 0) + by_risk.get("Crítico", 0) >= 5:
        recs.append("Volume relevante de risco Alto/Crítico no período. Considerar reforço da equipe de Ouvidoria.")
    if not recs:
        recs.append("Nenhuma ação prioritária identificada no período analisado.")
    return recs
