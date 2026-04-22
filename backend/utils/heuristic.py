from data.cities import cities
import math
#2 radius of the sphere arcsin( sqrt(sin^2((lat2-lat1)/2) + cos(lat1)*cos(lat2)*sin^2((lon2-lon1)/2)) )
def heuristic(city1, city2):
    lat1 = math.radians(cities[city1].lat)
    lon1 = math.radians(cities[city1].lon)

    lat2 = math.radians(cities[city2].lat)
    lon2 = math.radians(cities[city2].lon)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r  