def search_data(query: str, data: list, top_k: int = 5):
    query = query.lower().split()

    scored = []

    for row in data:
        score = sum(1 for word in query if word in row)
        scored.append((row, score))

    # sort by relevance
    scored.sort(key=lambda x: x[1], reverse=True)

    # return only top rows
    return [row for row, score in scored[:top_k]]