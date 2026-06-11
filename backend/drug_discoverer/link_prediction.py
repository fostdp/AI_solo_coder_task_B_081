import networkx as nx
import numpy as np
from typing import List, Dict, Tuple
from collections import defaultdict


class LinkPredictor:
    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.nodes = list(graph.nodes())
        self.node_index = {node: i for i, node in enumerate(self.nodes)}

    def common_neighbors(self, node_a, node_b) -> int:
        neighbors_a = set(self.graph.neighbors(node_a))
        neighbors_b = set(self.graph.neighbors(node_b))
        return len(neighbors_a & neighbors_b)

    def jaccard_coefficient(self, node_a, node_b) -> float:
        neighbors_a = set(self.graph.neighbors(node_a))
        neighbors_b = set(self.graph.neighbors(node_b))
        intersection = len(neighbors_a & neighbors_b)
        union = len(neighbors_a | neighbors_b)
        return intersection / union if union > 0 else 0.0

    def adamic_adar(self, node_a, node_b) -> float:
        neighbors_a = set(self.graph.neighbors(node_a))
        neighbors_b = set(self.graph.neighbors(node_b))
        common = neighbors_a & neighbors_b
        
        score = 0.0
        for node in common:
            degree = self.graph.degree(node)
            if degree > 1:
                score += 1 / np.log(degree)
        return score

    def resource_allocation(self, node_a, node_b) -> float:
        neighbors_a = set(self.graph.neighbors(node_a))
        neighbors_b = set(self.graph.neighbors(node_b))
        common = neighbors_a & neighbors_b
        
        score = 0.0
        for node in common:
            degree = self.graph.degree(node)
            if degree > 0:
                score += 1 / degree
        return score

    def preferential_attachment(self, node_a, node_b) -> float:
        degree_a = self.graph.degree(node_a)
        degree_b = self.graph.degree(node_b)
        return degree_a * degree_b

    def katz_index(self, beta: float = 0.001, max_path: int = 3) -> Dict[Tuple, float]:
        n = len(self.nodes)
        adj_matrix = np.zeros((n, n))
        
        for i, node in enumerate(self.nodes):
            for neighbor in self.graph.neighbors(node):
                j = self.node_index[neighbor]
                adj_matrix[i][j] = 1
        
        scores = defaultdict(float)
        current_matrix = adj_matrix.copy()
        
        for k in range(1, max_path + 1):
            for i in range(n):
                for j in range(i + 1, n):
                    if not self.graph.has_edge(self.nodes[i], self.nodes[j]):
                        scores[(self.nodes[i], self.nodes[j])] += (beta ** k) * current_matrix[i][j]
            current_matrix = np.dot(current_matrix, adj_matrix)
        
        return dict(scores)

    def predict_links(self, method: str = "adamic_adar", top_n: int = 50) -> List[Dict]:
        predictions = []
        
        non_edges = list(nx.non_edges(self.graph))
        
        for node_a, node_b in non_edges:
            if method == "common_neighbors":
                score = self.common_neighbors(node_a, node_b)
            elif method == "jaccard":
                score = self.jaccard_coefficient(node_a, node_b)
            elif method == "adamic_adar":
                score = self.adamic_adar(node_a, node_b)
            elif method == "resource_allocation":
                score = self.resource_allocation(node_a, node_b)
            elif method == "preferential_attachment":
                score = self.preferential_attachment(node_a, node_b)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            predictions.append({
                "herb_a": node_a,
                "herb_b": node_b,
                "score": round(score, 6),
                "method": method
            })
        
        predictions.sort(key=lambda x: -x["score"])
        return predictions[:top_n]

    def predict_with_targets(self, herb_targets: Dict[str, List[str]], top_n: int = 50) -> List[Dict]:
        predictions = []
        
        non_edges = list(nx.non_edges(self.graph))
        
        for node_a, node_b in non_edges:
            targets_a = set(herb_targets.get(node_a, []))
            targets_b = set(herb_targets.get(node_b, []))
            
            common_targets = len(targets_a & targets_b)
            all_targets = len(targets_a | targets_b)
            target_similarity = common_targets / all_targets if all_targets > 0 else 0.0
            
            aa_score = self.adamic_adar(node_a, node_b)
            jaccard_score = self.jaccard_coefficient(node_a, node_b)
            
            combined_score = 0.4 * aa_score + 0.3 * jaccard_score + 0.3 * target_similarity
            
            predictions.append({
                "herb_a": node_a,
                "herb_b": node_b,
                "score": round(combined_score, 6),
                "adamic_adar": round(aa_score, 6),
                "jaccard": round(jaccard_score, 6),
                "target_similarity": round(target_similarity, 6),
                "common_targets": common_targets,
                "method": "combined"
            })
        
        predictions.sort(key=lambda x: -x["score"])
        return predictions[:top_n]

    def predict_support_confidence(self, herb_a: str, herb_b: str, transactions: List[List[str]]) -> Dict:
        total = len(transactions)
        
        count_a = sum(1 for t in transactions if herb_a in t)
        count_b = sum(1 for t in transactions if herb_b in t)
        count_ab = sum(1 for t in transactions if herb_a in t and herb_b in t)
        
        support_ab = count_ab / total if total > 0 else 0
        confidence_ab = count_ab / count_a if count_a > 0 else 0
        confidence_ba = count_ab / count_b if count_b > 0 else 0
        lift = support_ab / ((count_a / total) * (count_b / total)) if count_a > 0 and count_b > 0 else 0
        
        aa_score = self.adamic_adar(herb_a, herb_b)
        jaccard = self.jaccard_coefficient(herb_a, herb_b)
        
        return {
            "herb_a": herb_a,
            "herb_b": herb_b,
            "support": round(support_ab, 4),
            "confidence_a_to_b": round(confidence_ab, 4),
            "confidence_b_to_a": round(confidence_ba, 4),
            "lift": round(lift, 4),
            "adamic_adar": round(aa_score, 6),
            "jaccard": round(jaccard, 4),
            "co_occurrence_count": count_ab
        }
