"""
Dynamic Network Graph Features.

Represents the network as a dynamic graph G(t) with nodes as hosts/IPs
and edges as active communication relationships. Extracts topological
features and their temporal changes.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


class DynamicGraph:
    """Maintains a dynamic graph across time windows."""
    
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.edge_history: List[Set[Tuple[str, str]]] = []
        self.node_history: List[Set[str]] = []
        self.prev_graph_features: Optional[Dict[str, float]] = None
    
    def update(self, records: List[Dict]) -> Dict[str, float]:
        """Update graph with new window's records and compute features."""
        # Extract edges and nodes from current window
        edges = set()
        nodes = set()
        
        for r in records:
            src = r.get("src_ip", "")
            dst = r.get("dst_ip", "")
            if src and dst:
                edges.add((src, dst))
                nodes.add(src)
                nodes.add(dst)
        
        self.edge_history.append(edges)
        self.node_history.append(nodes)
        
        # Trim history
        if len(self.edge_history) > self.max_history:
            self.edge_history = self.edge_history[-self.max_history:]
            self.node_history = self.node_history[-self.max_history:]
        
        # Compute features
        features = self._compute_features(edges, nodes)
        
        # Compute temporal derivatives
        if self.prev_graph_features:
            for key in ["density", "avg_degree", "node_count", "edge_count"]:
                curr = features.get(key, 0.0)
                prev = self.prev_graph_features.get(key, 0.0)
                features[f"{key}_delta"] = curr - prev
        else:
            for key in ["density", "avg_degree", "node_count", "edge_count"]:
                features[f"{key}_delta"] = 0.0
        
        self.prev_graph_features = {k: v for k, v in features.items() 
                                    if k in ["density", "avg_degree", "node_count", "edge_count"]}
        
        return features
    
    def _compute_features(self, edges: Set[Tuple[str, str]], 
                          nodes: Set[str]) -> Dict[str, float]:
        """Compute graph topology features."""
        node_count = len(nodes)
        edge_count = len(edges)
        
        # Graph density
        max_edges = node_count * (node_count - 1) if node_count > 1 else 1
        density = edge_count / max_edges
        
        # Degree statistics
        degrees = defaultdict(int)
        for src, dst in edges:
            degrees[src] += 1
            degrees[dst] += 1
        
        degree_values = list(degrees.values())
        avg_degree = np.mean(degree_values) if degree_values else 0.0
        degree_variance = np.var(degree_values) if degree_values else 0.0
        
        # New/removed edges compared to previous window
        new_edges = 0
        removed_edges = 0
        if len(self.edge_history) >= 2:
            prev_edges = self.edge_history[-2]
            new_edges = len(edges - prev_edges)
            removed_edges = len(prev_edges - edges)
        
        # New destinations/sources
        new_destinations = 0
        new_sources = 0
        if len(self.node_history) >= 2:
            prev_nodes = self.node_history[-2]
            new_destinations = len(nodes - prev_nodes)
            new_sources = len(nodes - prev_nodes)  # Same for undirected
        
        # Clustering coefficient (simplified)
        clustering = self._clustering_coefficient(edges, nodes)
        
        # Centrality approximations (computationally light)
        eigenvector_centrality_max = self._approx_eigenvector_centrality(edges, nodes)
        betweenness_centrality_max = self._approx_betweenness_centrality(edges, nodes)
        pagerank_max = self._approx_pagerank(edges, nodes)
        
        return {
            "node_count": float(node_count),
            "edge_count": float(edge_count),
            "graph_density": float(density),
            "average_degree": float(avg_degree),
            "degree_variance": float(degree_variance),
            "clustering_coefficient": float(clustering),
            "new_edges": float(new_edges),
            "removed_edges": float(removed_edges),
            "new_destinations": float(new_destinations),
            "new_sources": float(new_sources),
            "eigenvector_centrality_max": float(eigenvector_centrality_max),
            "betweenness_centrality_max": float(betweenness_centrality_max),
            "pagerank_max": float(pagerank_max),
            "new_edges_rate": float(new_edges) / max(1, edge_count),
            "new_destinations_rate": float(new_destinations) / max(1, node_count),
        }
    
    def _clustering_coefficient(self, edges: Set[Tuple[str, str]], 
                                nodes: Set[str]) -> float:
        """Approximate clustering coefficient."""
        if len(nodes) < 3:
            return 0.0
        
        # Build adjacency
        adj = defaultdict(set)
        for u, v in edges:
            adj[u].add(v)
            adj[v].add(u)
        
        total_cc = 0.0
        count = 0
        for node in nodes:
            neighbors = adj[node]
            k = len(neighbors)
            if k < 2:
                continue
            # Count edges between neighbors
            links = 0
            neighbor_list = list(neighbors)
            for i in range(k):
                for j in range(i + 1, k):
                    if neighbor_list[j] in adj[neighbor_list[i]]:
                        links += 1
            max_links = k * (k - 1) / 2
            total_cc += links / max_links
            count += 1
        
        return total_cc / count if count > 0 else 0.0
    
    def _approx_eigenvector_centrality(self, edges: Set[Tuple[str, str]], 
                                        nodes: Set[str], 
                                        iterations: int = 10) -> float:
        """Approximate eigenvector centrality using power iteration."""
        if not nodes:
            return 0.0
        
        adj = defaultdict(set)
        for u, v in edges:
            adj[u].add(v)
            adj[v].add(u)
        
        # Initialize
        centrality = {n: 1.0 for n in nodes}
        
        for _ in range(iterations):
            new_centrality = {}
            for n in nodes:
                total = sum(centrality.get(nbr, 0) for nbr in adj[n])
                new_centrality[n] = total
            
            # Normalize
            max_val = max(new_centrality.values()) if new_centrality else 1.0
            if max_val > 0:
                centrality = {n: v / max_val for n, v in new_centrality.items()}
            else:
                break
        
        return max(centrality.values()) if centrality else 0.0
    
    def _approx_betweenness_centrality(self, edges: Set[Tuple[str, str]], 
                                        nodes: Set[str]) -> float:
        """Approximate betweenness centrality (simplified)."""
        if len(nodes) < 3:
            return 0.0
        
        adj = defaultdict(set)
        for u, v in edges:
            adj[u].add(v)
            adj[v].add(u)
        
        # Simple approximation: node with highest degree tends to have high betweenness
        degrees = {n: len(adj[n]) for n in nodes}
        if not degrees:
            return 0.0
        
        max_degree = max(degrees.values())
        # Normalize by n*(n-1)/2
        n = len(nodes)
        max_possible = n * (n - 1) / 2 if n > 1 else 1
        
        return max_degree / max_possible
    
    def _approx_pagerank(self, edges: Set[Tuple[str, str]], 
                          nodes: Set[str],
                          alpha: float = 0.85,
                          iterations: int = 10) -> float:
        """Approximate PageRank."""
        if not nodes:
            return 0.0
        
        adj = defaultdict(set)
        out_degree = defaultdict(int)
        for u, v in edges:
            adj[u].add(v)
            out_degree[u] += 1
        
        # Initialize
        pr = {n: 1.0 / len(nodes) for n in nodes}
        
        for _ in range(iterations):
            new_pr = {}
            for n in nodes:
                rank = (1 - alpha) / len(nodes)
                # Sum contributions from in-neighbors
                for m in nodes:
                    if n in adj[m] and out_degree[m] > 0:
                        rank += alpha * pr[m] / out_degree[m]
                new_pr[n] = rank
            pr = new_pr
        
        return max(pr.values()) if pr else 0.0


def compute_graph_features(records: List[Dict],
                            graph_state: Optional[DynamicGraph] = None) -> Tuple[Dict[str, float], DynamicGraph]:
    """
    Compute dynamic graph features from records.
    
    Args:
        records: List of packet/flow dicts
        graph_state: Optional existing DynamicGraph to continue
    
    Returns:
        (features_dict, updated_DynamicGraph)
    """
    if graph_state is None:
        graph_state = DynamicGraph()
    
    features = graph_state.update(records)
    return features, graph_state


def _empty_graph_features() -> Dict[str, float]:
    keys = [
        "node_count", "edge_count", "graph_density", "average_degree",
        "degree_variance", "clustering_coefficient", "new_edges",
        "removed_edges", "new_destinations", "new_sources",
        "eigenvector_centrality_max", "betweenness_centrality_max",
        "pagerank_max", "new_edges_rate", "new_destinations_rate",
        "density_delta", "avg_degree_delta", "node_count_delta", "edge_count_delta",
    ]
    return {k: 0.0 for k in keys}