
"""
Package Detection Utilities.
"""
import os
from typing import List


def find_connected_groups(nodes: List[str], adjacency: dict) -> tuple:
    """
    Identifies connected components (groups) and isolated nodes in a package graph 
    using Depth First Search (DFS).
    Args:
        nodes: List of node names (strings) corresponding to indices 0..m-1
        adjacency: Dict where key is node index (int) and value is set of neighbor indices (Set[int])
        
    Returns:
        tuple(groups, isolated_nodes)
        - groups: List of lists, where each inner list contains node names of a connected group.
        - isolated_nodes: List of node names that have no connections.
    """
    m = len(nodes)
    visited = set()
    groups = []
    for i in range(m):
        if i not in visited:
            # Check if it has any edges (connected component of size > 1)
            # OR if it is a single island.
            if i in adjacency or any(i in adj_set for adj_set in adjacency.values()):
                 # It is part of a graph structure (even if self-loop, theoretically)
                 # Start DFS
                 component = []
                 stack = [i]
                 visited.add(i)
                 while stack:
                     curr = stack.pop()
                     component.append(nodes[curr])
                     # Get neighbors
                     neighbors = adjacency.get(curr, set())
                     for neighbor in neighbors:
                         if neighbor not in visited:
                             visited.add(neighbor)
                             stack.append(neighbor)
                 groups.append(component)
            else:
                 # It's an isolated node (not in adjacency keys or values)
                 # However, the DFS logic handles single-node components too. 
                 # To distinguish "Group of 1" vs "Isolated", strictly speaking:
                 # If we iterate 0..m, any unvisited node starts a new component.
                 # The metrics define "Isolated" as having 0 edges.
                 pass

    visited = set()
    all_components = []
    
    for i in range(m):
        if i not in visited:
            component_indices = []
            stack = [i]
            visited.add(i)
            while stack:
                curr = stack.pop()
                component_indices.append(curr)
                for neighbor in adjacency.get(curr, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            all_components.append(component_indices)
            
    groups = []
    isolated = []
    
    for comp_indices in all_components:
        comp_names = [nodes[idx] for idx in comp_indices]
        if len(comp_indices) > 1:
            groups.append(comp_names)
        else:
            # Size 1: Check if it has a self-loop or really isolated?
            # Metric def: Isolated if R[i][j] is false for all j!=i.
            # In our adjacency dict, usually only relevant edges are added.
            # If it's size 1, it's virtually always isolated in SCPP/FCPP context.
            isolated.extend(comp_names)
            
    # However, sometimes a group of size 1 IS valid if the graph had a self-connection?
    # No, typically irrelevant for cohesion.
    # But wait: SCPP/FCPP logic says "Isolated" if not in connected_indices keys.
    # Let's match exact SCPP/FCPP logic for consistency:
    
    connected_indices = set(adjacency.keys()) | {x for v in adjacency.values() for x in v}
    groups = []
    visited_connected = set()
    
    for i in range(m):
        if i in connected_indices and i not in visited_connected:
            comp = []
            stack = [i]
            visited_connected.add(i)
            while stack:
                curr = stack.pop()
                comp.append(nodes[curr])
                for neighbor in adjacency.get(curr, set()):
                    if neighbor not in visited_connected:
                        visited_connected.add(neighbor)
                        stack.append(neighbor)
            groups.append(comp)
            
    isolated_nodes = [nodes[i] for i in range(m) if i not in connected_indices]
    
    return groups, isolated_nodes

# def transverse_tree_to_get_packages_and_files(node,current_path="",dir_list=None):
#     if node["type"]=="file" and node["name"].endswith(".py") and node["name"]!="__init__.py":
#         return node["path"].replace("/","",1)
#     packages_file_path=[]
#     if "children" in node:
#         for child in node["children"]:
#             module=transverse_tree_to_get_packages_and_files(child,node["path"],dir_list)
#             if isinstance(module,list):
#                 packages_file_path.extend(module)
#             else:
#                 packages_file_path.append(module)
#     if node["type"]=="directory" and node["type"]!="/":
#         dir_list.append({
#             "path":node["path"].replace("/","",1),
#             "files":packages_file_path
#         })
#     return packages_file_path
    
    
