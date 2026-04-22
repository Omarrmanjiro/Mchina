import heapq
from data.graph import graph
from utils.heuristic import heuristic

def astar(start, goal):
    # Priority queue to store the nodes to explore
    open_set = []
    heapq.heappush(open_set, (0 , start))
    
    # Dictionary to store the parent of each node for path reconstruction
    came_from = {}
    
    g_score = {city: float('inf') for city in graph}
    g_score[start] = 0

    f_score = {city: float('inf') for city in graph}
    # The f_score equals the g_score = 0 at the beginning plus the heuristic estimate to the goal
    f_score[start] = heuristic(start, goal)

    visited = []

    while open_set:
        # The node in the open set with the lowest f_score value _ used to ignore other values
        _,current = heapq.heappop(open_set)
        if current not in visited:
            visited.append(current)
        #construct the path after reaching the goal
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                #fetch the parent of the current node 
                current = came_from[current]
            path.append(start)
            path.reverse()
            return {"path": path,"distance": g_score[goal], "visited": visited}
            
        for neighbor, distance in graph[current]:
            tentative_g = g_score[current] + distance
            if tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g

                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    return None