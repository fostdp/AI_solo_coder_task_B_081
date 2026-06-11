from itertools import combinations
from typing import List, Dict, Set, Tuple
from collections import defaultdict


class FPNode:
    __slots__ = ['item', 'count', 'parent', 'children', 'next']

    def __init__(self, item=None, count=0, parent=None):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}
        self.next = None


class FPTree:
    def __init__(self):
        self.root = FPNode()
        self.header_table = defaultdict(list)
        self.item_counts = defaultdict(int)

    def add_transaction(self, transaction: List[str], count: int = 1):
        current = self.root
        for item in transaction:
            self.item_counts[item] += count
            if item in current.children:
                current.children[item].count += count
                current = current.children[item]
            else:
                new_node = FPNode(item, count, current)
                current.children[item] = new_node
                self._link_header(new_node)
                current = new_node

    def _link_header(self, node: FPNode):
        self.header_table[node.item].append(node)

    def get_prefix_paths(self, item: str) -> List[Tuple[List[str], int]]:
        paths = []
        for node in self.header_table[item]:
            path = []
            current = node.parent
            while current.item is not None:
                path.append(current.item)
                current = current.parent
            if path:
                paths.append((list(reversed(path)), node.count))
        return paths

    def is_single_path(self) -> bool:
        current = self.root
        while current:
            if len(current.children) > 1:
                return False
            if len(current.children) == 0:
                return True
            current = list(current.children.values())[0]
        return True


class FPGrowth:
    def __init__(
        self,
        min_support: float = 0.1,
        min_confidence: float = 0.5,
        min_lift: float = 1.0,
        max_itemset_length: int = 3
    ):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.max_itemset_length = max_itemset_length
        self.freq_itemsets = {}
        self.total_transactions = 0

    def fit(self, transactions: List[List[str]]):
        self.total_transactions = len(transactions)
        min_count = self.min_support * self.total_transactions

        item_counts = defaultdict(int)
        for transaction in transactions:
            for item in transaction:
                item_counts[item] += 1

        freq_items = {
            item: count
            for item, count in item_counts.items()
            if count >= min_count
        }

        if not freq_items:
            self.freq_itemsets = {}
            return {}, {}

        sorted_items = sorted(freq_items.items(), key=lambda x: (-x[1], x[0]))
        item_order = {item: i for i, (item, _) in enumerate(sorted_items)}

        ordered_transactions = []
        for transaction in transactions:
            ordered = [
                item for item in sorted(
                    [item for item in transaction if item in freq_items],
                    key=lambda x: item_order[x]
                )
            ]
            if ordered:
                ordered_transactions.append(ordered)

        tree = FPTree()
        for transaction in ordered_transactions:
            tree.add_transaction(transaction)

        all_freq = {}

        for item, count in freq_items.items():
            all_freq[frozenset([item])] = count / self.total_transactions

        if self.max_itemset_length >= 2:
            self._mine_tree(tree, set(), min_count, all_freq)

        self.freq_itemsets = all_freq
        support_data = {
            k: int(v * self.total_transactions)
            for k, v in all_freq.items()
        }
        return all_freq, support_data

    def _mine_tree(
        self,
        tree: FPTree,
        suffix: frozenset,
        min_count: float,
        all_freq: Dict
    ):
        if tree.is_single_path():
            items = []
            current = tree.root
            while current:
                if current.item is not None:
                    items.append((current.item, current.count))
                if current.children:
                    current = list(current.children.values())[0]
                else:
                    current = None

            for i in range(1, len(items) + 1):
                if len(suffix) + i > self.max_itemset_length:
                    break
                for combo in combinations(range(len(items)), i):
                    min_cnt = min(items[idx][1] for idx in combo)
                    if min_cnt >= min_count:
                        itemset = frozenset(
                            [items[idx][0] for idx in combo]
                        ) | suffix
                        if len(itemset) <= self.max_itemset_length:
                            support = min_cnt / self.total_transactions
                            if support >= self.min_support:
                                all_freq[itemset] = support
            return

        sorted_items = sorted(
            tree.header_table.keys(),
            key=lambda x: tree.item_counts.get(x, 0)
        )

        for item in sorted_items:
            new_suffix = frozenset([item]) | suffix
            if len(new_suffix) > self.max_itemset_length:
                continue

            paths = tree.get_prefix_paths(item)
            if not paths:
                continue

            conditional_tree = FPTree()
            for path, count in paths:
                filtered = [
                    i for i in path
                    if tree.item_counts.get(i, 0) >= min_count
                ]
                if filtered:
                    conditional_tree.add_transaction(filtered, count)

            item_count = sum(count for _, count in paths)
            support = item_count / self.total_transactions
            if support >= self.min_support:
                all_freq[new_suffix] = support

            if conditional_tree.header_table:
                if len(new_suffix) < self.max_itemset_length:
                    self._mine_tree(
                        conditional_tree, new_suffix, min_count, all_freq
                    )

    def generate_rules(self) -> List[Dict]:
        rules = []
        for freq_set in self.freq_itemsets:
            k = len(freq_set)
            if k < 2:
                continue
            for i in range(1, k):
                for antecedent in combinations(freq_set, i):
                    antecedent_set = frozenset(antecedent)
                    consequent_set = freq_set - antecedent_set
                    if not consequent_set:
                        continue
                    if antecedent_set not in self.freq_itemsets:
                        continue
                    if consequent_set not in self.freq_itemsets:
                        continue

                    support = self.freq_itemsets[freq_set]
                    confidence = (
                        support / self.freq_itemsets[antecedent_set]
                    )
                    lift = (
                        confidence / self.freq_itemsets[consequent_set]
                    )

                    if (
                        confidence >= self.min_confidence
                        and lift >= self.min_lift
                    ):
                        rules.append({
                            "antecedent": sorted(list(antecedent_set)),
                            "consequent": sorted(list(consequent_set)),
                            "support": round(support, 4),
                            "confidence": round(confidence, 4),
                            "lift": round(lift, 4)
                        })

        rules.sort(key=lambda x: (-x["support"], -x["confidence"]))
        return rules

    def get_top_pairs(self, n: int = 20) -> List[Dict]:
        pairs = []
        for freq_set, support in self.freq_itemsets.items():
            if len(freq_set) == 2:
                items = sorted(list(freq_set))
                pairs.append({
                    "herb_a": items[0],
                    "herb_b": items[1],
                    "support": round(support, 4),
                    "count": int(support * self.total_transactions)
                })
        pairs.sort(key=lambda x: -x["support"])
        return pairs[:n]

    def get_top_triplets(self, n: int = 20) -> List[Dict]:
        triplets = []
        for freq_set, support in self.freq_itemsets.items():
            if len(freq_set) == 3:
                items = sorted(list(freq_set))
                triplets.append({
                    "herbs": items,
                    "support": round(support, 4),
                    "count": int(support * self.total_transactions)
                })
        triplets.sort(key=lambda x: -x["support"])
        return triplets[:n]
