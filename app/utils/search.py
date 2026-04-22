def normalize_query(query: str):
    query = query.lower()

    replacements = {
        "os": "operating system",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "dl": "deep learning",
        "dbms": "database management system",
        "cn": "computer network"
    }

    for k, v in replacements.items():
        query = query.replace(k, v)

    return query
def search_data(query: str, data: list, top_k: int = 3):
    query = normalize_query(query)
    query_words = query.split()

    scored = []

    for row in data:

        # 🔥 combine all searchable fields
        text = f"{row['subject']} {row['topic']} {row['details']}".lower()

        score = sum(1 for word in query_words if word in text)

        if score > 0:
            scored.append((row, score))

    if not scored:
        return []

    scored.sort(key=lambda x: x[1], reverse=True)

    return [row for row, _ in scored[:top_k]]