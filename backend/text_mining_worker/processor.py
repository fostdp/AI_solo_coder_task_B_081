import re
import math
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import queue
import threading
import time
from uuid import uuid4

from adverse_event_miner.miner import AdverseReactionExtractor
from efficacy_scorer.scorer import (
    TCMSentimentAnalyzer,
    SentimentUncertaintyEstimator,
)


@dataclass
class MiningTask:
    task_id: str
    task_type: str
    text: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class AdverseEventTextMiner:

    REACTION_PATTERNS = AdverseReactionExtractor.REACTION_PATTERNS
    SEVERITY_WEIGHTS = AdverseReactionExtractor.SEVERITY_WEIGHTS

    @classmethod
    def extract_from_text(cls, text: str) -> List[Dict[str, Any]]:
        return AdverseReactionExtractor.extract_from_text(text)

    @classmethod
    def batch_extract(cls, texts: List[str]) -> List[List[Dict[str, Any]]]:
        return [cls.extract_from_text(t) for t in texts]

    @classmethod
    def aggregate_reactions(cls, reactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_reactions = []
        severity_counts = Counter()
        for r in reactions:
            reaction_entry = {
                "reaction_type": r.get("type", r.get("reaction_type", "未知")),
                "severity": r.get("severity", "轻度"),
                **r,
            }
            all_reactions.append(reaction_entry)
            severity_counts[reaction_entry["severity"]] += 1
        by_type = defaultdict(list)
        for r in all_reactions:
            by_type[r["reaction_type"]].append(r)
        return {
            "total_reactions": len(all_reactions),
            "severity_distribution": dict(severity_counts),
            "by_reaction_type": dict(by_type),
            "all_reactions": all_reactions,
        }


class EfficacyTextAnalyzer:

    POSITIVE_KEYWORDS = TCMSentimentAnalyzer.POSITIVE_KEYWORDS
    NEGATIVE_KEYWORDS = TCMSentimentAnalyzer.NEGATIVE_KEYWORDS
    NEGATION_PREFIXES = TCMSentimentAnalyzer.NEGATION_PREFIXES
    INTENSIFIERS = TCMSentimentAnalyzer.INTENSIFIERS
    TIME_PATTERNS = TCMSentimentAnalyzer.TIME_PATTERNS

    @classmethod
    def compute_sentiment(cls, text: str) -> float:
        return TCMSentimentAnalyzer.compute_sentiment(text)

    @classmethod
    def extract_days(cls, text: str) -> Optional[int]:
        return TCMSentimentAnalyzer.extract_days(text)

    @staticmethod
    def keyword_entropy(matched_keywords: List[Tuple[str, float, str]]) -> float:
        return SentimentUncertaintyEstimator.keyword_entropy(matched_keywords)

    @staticmethod
    def confidence_from_matches(n_matches: int, text_length: int) -> float:
        return SentimentUncertaintyEstimator.confidence_from_matches(n_matches, text_length)

    @classmethod
    def analyze_with_uncertainty(cls, text: str) -> Dict[str, Any]:
        return TCMSentimentAnalyzer.analyze_with_uncertainty(text)

    @classmethod
    def batch_analyze(cls, texts: List[str]) -> List[Dict[str, Any]]:
        return [cls.analyze_with_uncertainty(t) for t in texts]


class TextMiningWorker:

    def __init__(self, max_queue_size: int = 1000, num_workers: int = 2):
        self.task_queue: "queue.Queue[MiningTask]" = queue.Queue(maxsize=max_queue_size)
        self.results: Dict[str, MiningTask] = {}
        self.num_workers = num_workers
        self.workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self.adverse_miner = AdverseEventTextMiner()
        self.efficacy_analyzer = EfficacyTextAnalyzer()

    def start(self):
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"TextMiner-{i}", daemon=True)
            t.start()
            self.workers.append(t)

    def stop(self):
        self._stop_event.set()
        for t in self.workers:
            t.join(timeout=1.0)
        self.workers.clear()

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=0.1)
                self._process_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = time.time()
                self.results[task.task_id] = task

    def _process_task(self, task: MiningTask):
        task.status = "processing"
        try:
            if task.task_type == "adverse_extract":
                result = self.adverse_miner.extract_from_text(task.text)
                task.result = {"extracted_reactions": result, "count": len(result)}
            elif task.task_type == "efficacy_analyze":
                result = self.efficacy_analyzer.analyze_with_uncertainty(task.text)
                task.result = result
            elif task.task_type == "batch_adverse":
                texts = task.context.get("texts", [task.text])
                result = self.adverse_miner.batch_extract(texts)
                task.result = {"batch_results": result, "total": len(result)}
            elif task.task_type == "batch_efficacy":
                texts = task.context.get("texts", [task.text])
                result = self.efficacy_analyzer.batch_analyze(texts)
                task.result = {"batch_results": result, "total": len(result)}
            else:
                raise ValueError(f"未知的任务类型: {task.task_type}")
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
        finally:
            task.completed_at = time.time()
            self.results[task.task_id] = task

    def submit_task(self, task_type: str, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        task_id = str(uuid4())
        task = MiningTask(
            task_id=task_id,
            task_type=task_type,
            text=text,
            context=context or {},
        )
        self.task_queue.put(task)
        self.results[task_id] = task
        return task_id

    def get_result(self, task_id: str) -> Optional[MiningTask]:
        return self.results.get(task_id)

    def get_queue_status(self) -> Dict[str, Any]:
        pending = sum(1 for t in self.results.values() if t.status == "pending")
        processing = sum(1 for t in self.results.values() if t.status == "processing")
        completed = sum(1 for t in self.results.values() if t.status == "completed")
        failed = sum(1 for t in self.results.values() if t.status == "failed")
        return {
            "queue_size": self.task_queue.qsize(),
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "workers_running": len(self.workers),
        }

    def cleanup_old_results(self, max_age_seconds: int = 3600):
        now = time.time()
        old_ids = [
            tid for tid, t in self.results.items()
            if t.completed_at and (now - t.completed_at) > max_age_seconds
        ]
        for tid in old_ids:
            del self.results[tid]
        return len(old_ids)
