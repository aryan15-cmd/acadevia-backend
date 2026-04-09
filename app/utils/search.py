def normalize_query(query: str):
    """Handle common abbreviations"""
    query = query.lower()

    replacements = {
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "dl": "deep learning",
        "dbms": "database management system"
    }

    for k, v in replacements.items():
        query = query.replace(k, v)

    return query


def search_data(query: str, data: list, top_k: int = 3):
    # 🔥 normalize query
    query = normalize_query(query)
    query_words = query.split()

    scored = []

    for row in data:
        score = 0

        for word in query_words:
            if word in row:
                score += 1

        # ✅ only keep relevant rows
        if score > 0:
            scored.append((row, score))

    # ❌ if nothing found
    if not scored:
        return []

    # ✅ sort by relevance
    scored.sort(key=lambda x: x[1], reverse=True)

    # ✅ return only rows (top_k reduced for token saving)
    return [row for row, _ in scored[:top_k]]