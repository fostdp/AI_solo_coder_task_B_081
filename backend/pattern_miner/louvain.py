import networkx as nx
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
import random
import copy


class LouvainCommunity:
    def __init__(self, resolution: float = 1.0, random_state: int = 42):
        self.resolution = resolution
        self.random_state = random_state
        self.communities = {}
        self.graph = None
        self.modularity = 0.0
        self._partition_cache = None
        self._cache_graph_hash = None

    def fit(self, graph: nx.Graph):
        self.graph = graph
        random.seed(self.random_state)

        communities = self._louvain_method(graph)
        self.communities = communities
        self.modularity = self._calculate_modularity_fast(graph, communities)
        return communities

    def fit_partitioned(self, graph: nx.Graph, partition_size: int = 100) -> Dict[int, List]:
        self.graph = graph
        random.seed(self.random_state)

        if graph.number_of_nodes() <= partition_size:
            self.fit(graph)
            return self.get_communities()

        partitions = self._partition_graph(graph, partition_size)
        merged_partition = {}

        for subgraph_nodes in partitions:
            subgraph = graph.subgraph(subgraph_nodes).copy()
            if subgraph.number_of_nodes() < 2:
                for node in subgraph_nodes:
                    merged_partition[node] = len(merged_partition)
                continue

            sub_communities = self._louvain_method(subgraph)
            offset = max(merged_partition.values(), default=-1) + 1
            for node, comm in sub_communities.items():
                merged_partition[node] = comm + offset

        merged_partition = self._refine_partition(graph, merged_partition)

        self.communities = merged_partition
        self.modularity = self._calculate_modularity_fast(graph, merged_partition)
        return self.get_communities()

    def _partition_graph(self, graph: nx.Graph, partition_size: int) -> List[List]:
        nodes = list(graph.nodes())
        random.shuffle(nodes)

        partitions = []
        current_partition = []
        visited = set()

        for start_node in nodes:
            if start_node in visited:
                continue

            component = []
            queue = [start_node]
            while queue and len(component) < partition_size:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)

                neighbors = list(graph.neighbors(node))
                random.shuffle(neighbors)
                for neighbor in neighbors:
                    if neighbor not in visited and neighbor not in queue:
                        queue.append(neighbor)

            if component:
                partitions.append(component)

        remaining = [n for n in nodes if n not in visited]
        if remaining:
            for node in remaining:
                if partitions:
                    partitions[-1].append(node)
                else:
                    partitions.append([node])

        return partitions

    def _refine_partition(
        self,
        graph: nx.Graph,
        initial_partition: Dict,
        max_iterations: int = 5
    ) -> Dict:
        partition = dict(initial_partition)
        has_weight = self._has_weight(graph)
        m2 = self._get_total_weight(graph) * 2
        if m2 == 0:
            return partition

        node_degrees = {}
        community_weights = defaultdict(float)
        internal_weights = defaultdict(float)

        for node in graph.nodes():
            deg = graph.degree(node, weight='weight') if has_weight else graph.degree(node)
            node_degrees[node] = deg
            comm = partition[node]
            community_weights[comm] += deg

        for u, v, data in graph.edges(data=True):
            w = data.get('weight', 1) if has_weight else 1
            if partition[u] == partition[v]:
                internal_weights[partition[u]] += w

        for _ in range(max_iterations):
            improved = False
            nodes = list(graph.nodes())
            random.shuffle(nodes)

            for node in nodes:
                current_comm = partition[node]
                k_i = node_degrees[node]

                neighbor_comms = defaultdict(float)
                for neighbor in graph.neighbors(node):
                    w = graph.edges[node, neighbor].get('weight', 1) if has_weight else 1
                    neighbor_comms[partition[neighbor]] += w

                best_comm = current_comm
                best_delta = 0.0

                sigma_in = internal_weights.get(current_comm, 0)
                sigma_tot = community_weights[current_comm]
                k_i_in = neighbor_comms.get(current_comm, 0)

                removal_delta = (
                    (sigma_in - k_i_in) / m2 - ((sigma_tot - k_i) / m2) ** 2
                    - sigma_in / m2 + (sigma_tot / m2) ** 2 + (k_i / m2) ** 2
                )

                for target_comm, k_i_in_target in neighbor_comms.items():
                    if target_comm == current_comm:
                        continue

                    sigma_in_t = internal_weights.get(target_comm, 0)
                    sigma_tot_t = community_weights[target_comm]

                    insertion_delta = (
                        (sigma_in_t + k_i_in_target) / m2
                        - ((sigma_tot_t + k_i) / m2) ** 2
                        - sigma_in_t / m2 + (sigma_tot_t / m2) ** 2
                    )

                    delta = insertion_delta + removal_delta

                    if delta > best_delta:
                        best_delta = delta
                        best_comm = target_comm

                if best_comm != current_comm and best_delta > 0:
                    k_i_in_old = neighbor_comms.get(current_comm, 0)
                    k_i_in_new = neighbor_comms.get(best_comm, 0)

                    internal_weights[current_comm] -= k_i_in_old
                    internal_weights[best_comm] += k_i_in_new

                    community_weights[current_comm] -= k_i
                    community_weights[best_comm] += k_i

                    partition[node] = best_comm
                    improved = True

            if not improved:
                break

        return partition

    def fit_incremental(
        self,
        graph: nx.Graph,
        previous_partition: Optional[Dict] = None,
        changed_nodes: Optional[Set] = None
    ) -> Dict:
        self.graph = graph
        random.seed(self.random_state)

        if previous_partition is None:
            return self.fit(graph)

        partition = dict(previous_partition)

        for node in graph.nodes():
            if node not in partition:
                partition[node] = len(partition)

        if changed_nodes:
            for node in changed_nodes:
                partition[node] = len(partition) + hash(node) % 1000

        partition = self._refine_partition(graph, partition, max_iterations=3)

        self.communities = partition
        self.modularity = self._calculate_modularity_fast(graph, partition)
        return partition

    def _louvain_method(self, graph: nx.Graph) -> Dict[int, int]:
        partition = {node: i for i, node in enumerate(graph.nodes())}

        has_weight = self._has_weight(graph)
        m2 = self._get_total_weight(graph) * 2
        if m2 == 0:
            return partition

        node_degrees = {}
        community_weights = defaultdict(float)

        for node in graph.nodes():
            deg = graph.degree(node, weight='weight') if has_weight else graph.degree(node)
            node_degrees[node] = deg
            community_weights[partition[node]] += deg

        improvement = True
        max_rounds = 10
        round_count = 0

        while improvement and round_count < max_rounds:
            improvement = False
            round_count += 1

            nodes = list(graph.nodes())
            random.shuffle(nodes)

            for node in nodes:
                current_community = partition[node]
                k_i = node_degrees[node]

                neighbor_comms = defaultdict(float)
                for neighbor in graph.neighbors(node):
                    w = graph.edges[node, neighbor].get('weight', 1) if has_weight else 1
                    neighbor_comms[partition[neighbor]] += w

                best_community = current_community
                best_increase = 0.0

                sigma_tot_current = community_weights[current_community]
                k_i_in_current = neighbor_comms.get(current_community, 0)

                removal_gain = (
                    k_i_in_current / m2
                    - (sigma_tot_current * k_i) / (m2 * m2)
                )

                for community, k_i_in in neighbor_comms.items():
                    if community == current_community:
                        continue

                    sigma_tot = community_weights[community]

                    insertion_gain = (
                        k_i_in / m2
                        - (sigma_tot * k_i) / (m2 * m2)
                    )

                    delta_q = insertion_gain - removal_gain

                    if delta_q > best_increase:
                        best_increase = delta_q
                        best_community = community

                if best_increase > 0 and best_community != current_community:
                    community_weights[current_community] -= k_i
                    community_weights[best_community] += k_i
                    partition[node] = best_community
                    improvement = True

        unique_communities = list(set(partition.values()))
        community_mapping = {old: new for new, old in enumerate(unique_communities)}
        final_partition = {
            node: community_mapping[comm]
            for node, comm in partition.items()
        }

        return final_partition

    def _has_weight(self, graph: nx.Graph) -> bool:
        if graph.number_of_edges() == 0:
            return False
        first_edge = list(graph.edges(data=True))[0]
        return 'weight' in first_edge[2]

    def _get_total_weight(self, graph: nx.Graph) -> float:
        if self._has_weight(graph):
            return sum(
                data.get('weight', 1.0)
                for _, _, data in graph.edges(data=True)
            )
        return graph.number_of_edges()

    def _calculate_modularity_fast(
        self, graph: nx.Graph, partition: Dict[int, int]
    ) -> float:
        m2 = self._get_total_weight(graph) * 2
        if m2 == 0:
            return 0.0

        has_weight = self._has_weight(graph)
        communities = defaultdict(list)
        for node, comm in partition.items():
            communities[comm].append(node)

        Q = 0.0
        for comm, nodes in communities.items():
            sigma_in = 0.0
            sigma_tot = 0.0

            node_set = set(nodes)
            for node in nodes:
                for neighbor in graph.neighbors(node):
                    if neighbor in node_set:
                        w = (
                            graph.edges[node, neighbor].get('weight', 1)
                            if has_weight else 1
                        )
                        sigma_in += w
                    w = (
                        graph.edges[node, neighbor].get('weight', 1)
                        if has_weight else 1
                    )
                    sigma_tot += w

            Q += sigma_in / m2 - (sigma_tot / m2) ** 2

        return Q

    def get_communities(self) -> Dict[int, List]:
        community_groups = defaultdict(list)
        for node, comm_id in self.communities.items():
            community_groups[comm_id].append(node)
        return dict(community_groups)

    def get_community_sizes(self) -> Dict[int, int]:
        communities = self.get_communities()
        return {comm_id: len(nodes) for comm_id, nodes in communities.items()}

    def get_node_community(self, node) -> int:
        return self.communities.get(node, -1)
