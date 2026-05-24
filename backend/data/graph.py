import math

from data.cities import cities


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r = math.radians(lat1)
    lon1r = math.radians(lon1)
    lat2r = math.radians(lat2)
    lon2r = math.radians(lon2)

    dlat = lat2r - lat1r
    dlon = lon2r - lon1r

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return 6371.0 * c


def build_knn_graph(k: int = 5) -> dict[str, list[tuple[str, float]]]:
    names = list(cities.keys())
    graph: dict[str, list[tuple[str, float]]] = {name: [] for name in names}

    # For each city, connect it to its k nearest neighbors by great-circle distance.
    for name in names:
        src = cities[name]
        distances: list[tuple[str, float]] = []
        for other in names:
            if other == name:
                continue
            dst = cities[other]
            d = haversine_km(src.lat, src.lon, dst.lat, dst.lon)
            distances.append((other, d))
        distances.sort(key=lambda x: x[1])
        graph[name] = distances[: max(1, k)]

    # Make edges bidirectional (undirected) so A* can traverse both ways.
    for a, neighbors in list(graph.items()):
        for b, d in neighbors:
            if not any(x[0] == a for x in graph[b]):
                graph[b].append((a, d))

    # Keep neighbor lists stable / deterministic.
    for name in graph:
        graph[name].sort(key=lambda x: x[1])

    return graph


# Graph representation used by algorithms (A*)
graph = build_knn_graph(k=6)