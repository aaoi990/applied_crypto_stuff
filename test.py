import json
from pathlib import Path
from typing import List, Any, Union, Set, Dict, Tuple, Optional
import numpy as np
import random
from datasketch import MinHashLSHForest, MinHash
import heapq
from collections import defaultdict
import logging
import time
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ExperimentConfig:
    """Configuration for reproducible experiments"""
    num_perm: int = 128
    l: int = 32
    random_seed: int = 42
    filter_keys: List[str] = None
    use_lsh: bool = True
    lsh_threshold: int = 500  # Use LSH only for datasets larger than this
    candidates_per_round: int = 100  # How many candidates to consider each round
    chain_risk_enabled: bool = True  # Enable chain risk rejection
    chain_risk_k: int = 50  # Number of nearest neighbours to check
    chain_risk_threshold: float = 0.1  # Reject if this fraction of neighbours are already selected
    chain_risk_max_rejects: int = 5  # Max reselection attempts before accepting anyway
    
    def __post_init__(self):
        if self.filter_keys is None:
            self.filter_keys = ['id']

class ImprovedDiverseDataSelector:
    """
    Fixed implementation that properly uses LSH to reduce distance computations.
    
    Key improvements:
    1. Use LSH to find DISSIMILAR candidates (not similar)
    2. Only compute distances for LSH-filtered candidates
    3. Proper caching and incremental updates
    """
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.num_perm = config.num_perm
        self.l = config.l
        self.rng = random.Random(config.random_seed)
        self.np_rng = np.random.default_rng(config.random_seed)
        
        # MinHash LSH Forest
        self.lsh_forest = MinHashLSHForest(num_perm=self.num_perm, l=self.l)
        
        # Data storage
        self.data_entries = []
        self.minhashes = {}
        self.feature_sets = {}
        self.forest_indexed = False
        
        # Performance tracking
        self.distance_computations = 0
        self.lsh_queries = 0
        
        # Distance cache
        self.distance_cache = {}
        
        # Chain risk tracking
        self.chain_rejections = 0
        
        logger.info(f"Initialized ImprovedDiverseDataSelector with config: {config}")
    
    def parse_entry(self, entry: List[str]) -> Set[str]:
        """Parse entry into categorical features."""
        feature_set = set()
        for item in entry:
            if ':' in item:
                key, value = item.split(':', 1)
                if key.strip() not in self.config.filter_keys:
                    feature_set.add(item.strip())
        return feature_set
    
    def create_minhash(self, feature_set: Set[str]) -> MinHash:
        """Create MinHash signature."""
        minhash = MinHash(num_perm=self.num_perm, seed=self.config.random_seed)
        for feature in sorted(feature_set):
            minhash.update(feature.encode('utf8'))
        return minhash
    
    def load_data(self, data_entries: List[List[str]]) -> None:
        """Load and preprocess data entries."""
        start_time = time.time()
        logger.info(f"Loading {len(data_entries)} entries...")
        
        for i, entry in enumerate(data_entries):
            feature_set = self.parse_entry(entry)
            
            if len(feature_set) == 0:
                logger.warning(f"Empty feature set for entry {i}, skipping")
                continue
            
            minhash = self.create_minhash(feature_set)
            entry_id = f"entry_{i}"
            
            self.data_entries.append((entry_id, entry))
            self.minhashes[entry_id] = minhash
            self.feature_sets[entry_id] = feature_set
            
            # Add to LSH Forest
            self.lsh_forest.add(entry_id, minhash)
        
        # Build index
        self.lsh_forest.index()
        self.forest_indexed = True
        
        load_time = time.time() - start_time
        logger.info(f"Loaded {len(self.data_entries)} entries in {load_time:.2f}s")
    
    def compute_distance(self, id1: str, id2: str) -> float:
        """Compute Jaccard distance between two entries."""
        cache_key = tuple(sorted([id1, id2]))
        
        if cache_key not in self.distance_cache:
            self.distance_computations += 1
            set1 = self.feature_sets[id1]
            set2 = self.feature_sets[id2]
            
            if not set1 and not set2:
                dist = 0.0
            else:
                intersection_size = len(set1 & set2)
                union_size = len(set1 | set2)
                
                if union_size == 0:
                    dist = 0.0
                else:
                    jaccard_similarity = intersection_size / union_size
                    dist = 1.0 - jaccard_similarity
            
            self.distance_cache[cache_key] = dist
        
        return self.distance_cache[cache_key]
    
    def get_dissimilar_candidates_lsh(self, selected_ids: Set[str], 
                                     k: int = 100) -> List[str]:
        """
        Use LSH to find candidates that are DISSIMILAR to the selected set.
        
        Strategy: Find items that are NOT in the neighborhood of selected items.
        """
        self.lsh_queries += 1
        
        # Get all unselected entries
        all_unselected = set(eid for eid, _ in self.data_entries if eid not in selected_ids)
        
        if len(all_unselected) <= k:
            return list(all_unselected)
        
        # Find items that are SIMILAR to selected set (to exclude them)
        similar_to_selected = set()
        
        # Query from a sample of selected items to find their neighbors
        sample_size = min(10, len(selected_ids))
        sampled_selected = self.rng.sample(list(selected_ids), sample_size)
        
        for sel_id in sampled_selected:
            if sel_id in self.minhashes:
                # Find neighbors of this selected item
                neighbors = self.lsh_forest.query(self.minhashes[sel_id], k=50)
                similar_to_selected.update(neighbors)
        
        # Candidates are those NOT similar to selected set
        dissimilar_candidates = all_unselected - similar_to_selected
        
        if len(dissimilar_candidates) < k:
            # If we filtered too aggressively, add back some items
            remaining_needed = k - len(dissimilar_candidates)
            additional = list(similar_to_selected & all_unselected)[:remaining_needed]
            dissimilar_candidates = dissimilar_candidates.union(set(additional))
        
        # Return up to k candidates
        return list(dissimilar_candidates)[:k]
    
    def check_chain_risk(self, candidate_id: str, selected_ids: Set[str]) -> bool:
        """
        Check if a candidate has too many neighbours already in the selected set.
        
        Returns True if the candidate is a chain risk (should be rejected),
        False if it's safe to select.
        """
        if not self.config.chain_risk_enabled or not self.forest_indexed:
            return False
        
        if candidate_id not in self.minhashes:
            return False
        
        # Query LSH forest for nearest neighbours
        neighbours = self.lsh_forest.query(
            self.minhashes[candidate_id], 
            k=self.config.chain_risk_k + 1  # +1 because it may return itself
        )
        
        # Exclude the candidate itself from neighbours
        neighbours = [n for n in neighbours if n != candidate_id]
        
        if not neighbours:
            return False
        
        # Count how many neighbours are already selected
        selected_neighbours = sum(1 for n in neighbours if n in selected_ids)
        overlap_ratio = selected_neighbours / len(neighbours)
        
        is_risky = overlap_ratio >= self.config.chain_risk_threshold
        
        if is_risky:
            self.chain_rejections += 1
            logger.debug(
                f"Chain risk rejected {candidate_id}: "
                f"{selected_neighbours}/{len(neighbours)} neighbours already selected "
                f"({overlap_ratio:.1%} >= {self.config.chain_risk_threshold:.1%})"
            )
        
        return is_risky
    
    def find_diverse_subset_exact(self, target_count: int, 
                                   chain_aware: bool = True) -> List[Tuple[str, List[str]]]:
        """
        Exact greedy algorithm with optional chain-aware rejection.
        
        Uses farthest-first traversal with exact distance computation.
        When chain_aware=True and the LSH forest is indexed, candidates are
        checked for chain risk using LSH neighbour queries before acceptance.
        This gives exact-quality selection with LSH-powered chain breaking.
        """
        start_time = time.time()
        self.distance_computations = 0
        self.chain_rejections = 0
        self.distance_cache.clear()
        
        use_chain_check = (chain_aware and self.config.chain_risk_enabled 
                          and self.forest_indexed)
        
        if use_chain_check:
            logger.info("Chain-aware exact selection: using LSH forest for neighbour queries")
        
        if target_count > len(self.data_entries):
            target_count = len(self.data_entries)
        
        # Random seed
        seed_idx = self.rng.randint(0, len(self.data_entries) - 1)
        seed_id, seed_data = self.data_entries[seed_idx]
        
        selected_ids = {seed_id}
        selected_entries = [(seed_id, seed_data)]
        
        # Initialize min distances
        min_distances = {}
        for entry_id, _ in self.data_entries:
            if entry_id != seed_id:
                min_distances[entry_id] = self.compute_distance(entry_id, seed_id)
        
        # Build a lookup for entry data
        entry_data_lookup = {eid: data for eid, data in self.data_entries}
        
        # Main loop
        for iteration in range(1, target_count):
            # Sort all unselected candidates by min-distance descending
            candidates_sorted = sorted(
                ((eid, min_distances[eid]) for eid in min_distances if eid not in selected_ids),
                key=lambda x: x[1],
                reverse=True
            )
            
            if not candidates_sorted:
                logger.warning(f"No candidates at iteration {iteration}")
                break
            
            # Walk through candidates, reject chain risks
            best_candidate = None
            rejects = 0
            
            for cand_id, cand_dist in candidates_sorted:
                if use_chain_check and rejects < self.config.chain_risk_max_rejects:
                    if self.check_chain_risk(cand_id, selected_ids):
                        rejects += 1
                        continue
                
                best_candidate = cand_id
                break
            
            # Fallback — if all were rejected, take the farthest anyway
            if best_candidate is None:
                best_candidate = candidates_sorted[0][0]
            
            selected_ids.add(best_candidate)
            selected_entries.append((best_candidate, entry_data_lookup[best_candidate]))
            
            # Update min distances
            for entry_id in min_distances:
                if entry_id not in selected_ids:
                    dist_to_new = self.compute_distance(entry_id, best_candidate)
                    min_distances[entry_id] = min(min_distances[entry_id], dist_to_new)
            
            if iteration % 50 == 0:
                logger.info(f"Iteration {iteration}: {self.distance_computations} computations, "
                          f"{self.chain_rejections} chain rejections")
        
        elapsed = time.time() - start_time
        logger.info(f"Exact selection: {elapsed:.2f}s, {self.distance_computations} computations, "
                   f"{self.chain_rejections} chain rejections")
        
        return selected_entries
    
    def find_diverse_subset_lsh(self, target_count: int) -> List[Tuple[str, List[str]]]:
        """
        LSH-accelerated diverse subset selection.
        
        Key insight: Use LSH to filter candidates, not to find similar items.
        """
        start_time = time.time()
        self.distance_computations = 0
        self.lsh_queries = 0
        self.chain_rejections = 0
        self.distance_cache.clear()
        
        if target_count > len(self.data_entries):
            target_count = len(self.data_entries)
        
        # For small datasets, use exact method
        if len(self.data_entries) <= self.config.lsh_threshold:
            logger.info(f"Dataset size {len(self.data_entries)} <= {self.config.lsh_threshold}, using exact method")
            return self.find_diverse_subset_exact(target_count)
        
        # Random seed
        seed_idx = self.rng.randint(0, len(self.data_entries) - 1)
        seed_id, seed_data = self.data_entries[seed_idx]
        
        selected_ids = {seed_id}
        selected_entries = [(seed_id, seed_data)]
        
        # Track min distances only for active candidates
        active_candidates = {}  # id -> min_distance
        
        # Main loop
        for iteration in range(1, target_count):
            # Get candidates using LSH
            if iteration % 10 == 1 or len(active_candidates) < 20:
                # Refresh candidates periodically or when running low
                lsh_candidates = self.get_dissimilar_candidates_lsh(
                    selected_ids, 
                    k=self.config.candidates_per_round
                )
                
                # Initialize/update distances for new candidates
                for cand_id in lsh_candidates:
                    if cand_id not in active_candidates:
                        # Compute min distance to all selected items
                        min_dist = min(
                            self.compute_distance(cand_id, sel_id) 
                            for sel_id in selected_ids
                        )
                        active_candidates[cand_id] = min_dist
            
            # Find best candidate from active set
            if not active_candidates:
                # Fallback: get more candidates
                lsh_candidates = self.get_dissimilar_candidates_lsh(
                    selected_ids, 
                    k=self.config.candidates_per_round * 2
                )
                for cand_id in lsh_candidates:
                    min_dist = min(
                        self.compute_distance(cand_id, sel_id) 
                        for sel_id in selected_ids
                    )
                    active_candidates[cand_id] = min_dist
            
            if not active_candidates:
                logger.warning(f"No candidates at iteration {iteration}")
                break
            
            # Select farthest candidate, with chain risk rejection
            # Sort candidates by distance descending so we can try alternatives
            sorted_candidates = sorted(
                active_candidates.items(), key=lambda x: x[1], reverse=True
            )
            
            best_candidate = None
            rejects = 0
            for cand_id, cand_dist in sorted_candidates:
                if rejects >= self.config.chain_risk_max_rejects:
                    # Hit max rejects, accept this one anyway
                    best_candidate = cand_id
                    break
                
                if self.check_chain_risk(cand_id, selected_ids):
                    rejects += 1
                    continue
                
                best_candidate = cand_id
                break
            
            # Fallback if all were rejected (shouldn't happen due to max_rejects)
            if best_candidate is None:
                best_candidate = sorted_candidates[0][0]
            
            best_distance = active_candidates[best_candidate]
            best_data = next(data for eid, data in self.data_entries if eid == best_candidate)
            
            selected_ids.add(best_candidate)
            selected_entries.append((best_candidate, best_data))
            del active_candidates[best_candidate]
            
            # Update distances for remaining active candidates
            for cand_id in list(active_candidates.keys()):
                dist_to_new = self.compute_distance(cand_id, best_candidate)
                active_candidates[cand_id] = min(active_candidates[cand_id], dist_to_new)
                
                # Prune candidates that are too close
                if active_candidates[cand_id] < 0.1:  # Threshold for "too similar"
                    del active_candidates[cand_id]
            
            if iteration % 50 == 0:
                logger.info(f"Iteration {iteration}: {self.distance_computations} computations, "
                          f"{self.lsh_queries} LSH queries, {len(active_candidates)} active candidates, "
                          f"{self.chain_rejections} chain rejections")
        
        elapsed = time.time() - start_time
        logger.info(f"LSH selection: {elapsed:.2f}s, {self.distance_computations} computations, "
                   f"{self.lsh_queries} LSH queries, {self.chain_rejections} chain rejections")
        
        return selected_entries
    
    def calculate_diversity_metrics(self, selected_entries: List[Tuple[str, List[str]]]) -> Dict[str, float]:
        """Calculate diversity metrics."""
        if len(selected_entries) < 2:
            return {"error": "Need at least 2 entries"}
        
        entry_ids = [entry[0] for entry in selected_entries]
        distances = []
        
        for i in range(len(entry_ids)):
            for j in range(i + 1, len(entry_ids)):
                dist = self.compute_distance(entry_ids[i], entry_ids[j])
                distances.append(dist)
        
        distances = np.array(distances)
        
        return {
            "diversity_score": float(np.mean(distances)),
            "mean_pairwise_distance": float(np.mean(distances)),
            "std_pairwise_distance": float(np.std(distances)),
            "min_pairwise_distance": float(np.min(distances)),
            "max_pairwise_distance": float(np.max(distances)),
        }
    
    def compare_methods(self, target_count: int) -> Dict:
        """Compare exact, exact+chain-aware, and LSH methods."""
        logger.info("\n" + "="*60)
        logger.info("Comparing selection methods")
        logger.info("="*60)
        
        # Run exact method WITHOUT chain awareness (pure baseline)
        exact_selection = self.find_diverse_subset_exact(target_count, chain_aware=False)
        exact_metrics = self.calculate_diversity_metrics(exact_selection)
        exact_computations = self.distance_computations
        
        # Clear cache between runs
        self.distance_cache.clear()
        
        # Run exact method WITH chain awareness
        chain_selection = self.find_diverse_subset_exact(target_count, chain_aware=True)
        chain_metrics = self.calculate_diversity_metrics(chain_selection)
        chain_computations = self.distance_computations
        chain_rejections = self.chain_rejections
        
        # Clear cache between runs
        self.distance_cache.clear()
        
        # Run LSH method
        self.config.use_lsh = True
        lsh_selection = self.find_diverse_subset_lsh(target_count)
        lsh_metrics = self.calculate_diversity_metrics(lsh_selection)
        lsh_computations = self.distance_computations
        lsh_queries_count = self.lsh_queries
        
        # Calculate overlaps
        exact_ids = set(e[0] for e in exact_selection)
        chain_ids = set(e[0] for e in chain_selection)
        lsh_ids = set(e[0] for e in lsh_selection)
        
        results = {
            "exact": {
                "diversity_score": exact_metrics["diversity_score"],
                "computations": exact_computations,
                "mean_distance": exact_metrics["mean_pairwise_distance"]
            },
            "exact_chain_aware": {
                "diversity_score": chain_metrics["diversity_score"],
                "computations": chain_computations,
                "chain_rejections": chain_rejections,
                "mean_distance": chain_metrics["mean_pairwise_distance"]
            },
            "lsh": {
                "diversity_score": lsh_metrics["diversity_score"],
                "computations": lsh_computations,
                "lsh_queries": lsh_queries_count,
                "mean_distance": lsh_metrics["mean_pairwise_distance"]
            },
            "comparison": {
                "exact_vs_chain_overlap": len(exact_ids & chain_ids) / len(exact_ids) if exact_ids else 0,
                "exact_vs_lsh_overlap": len(exact_ids & lsh_ids) / len(exact_ids) if exact_ids else 0,
                "chain_vs_lsh_overlap": len(chain_ids & lsh_ids) / len(chain_ids) if chain_ids else 0,
            }
        }
        
        logger.info(f"\nResults:")
        logger.info(f"Exact:       {exact_computations:,} computations, "
                   f"diversity={exact_metrics['diversity_score']:.4f}")
        logger.info(f"Exact+Chain: {chain_computations:,} computations, "
                   f"{chain_rejections} rejections, "
                   f"diversity={chain_metrics['diversity_score']:.4f}")
        logger.info(f"LSH:         {lsh_computations:,} computations, "
                   f"{lsh_queries_count} queries, "
                   f"diversity={lsh_metrics['diversity_score']:.4f}")
        logger.info(f"Overlaps: exact↔chain={results['comparison']['exact_vs_chain_overlap']*100:.1f}%, "
                   f"exact↔lsh={results['comparison']['exact_vs_lsh_overlap']*100:.1f}%, "
                   f"chain↔lsh={results['comparison']['chain_vs_lsh_overlap']*100:.1f}%")
        
        return results
    
    def statistical_comparison_with_random(self, target_count: int, 
                                          num_trials: int = 100,
                                          use_lsh: bool = True) -> Dict:
        """
        Perform statistical comparison with random baseline.
        Tests whether the algorithm significantly outperforms random selection.
        """
        logger.info(f"\nRunning {num_trials} random trials for statistical comparison...")
        
        # Get algorithm selection (LSH or exact based on parameter)
        if use_lsh:
            algorithm_selection = self.find_diverse_subset_lsh(target_count)
            algorithm_name = "LSH"
        else:
            algorithm_selection = self.find_diverse_subset_exact(target_count)
            algorithm_name = "Exact"
            
        algorithm_metrics = self.calculate_diversity_metrics(algorithm_selection)
        algorithm_score = algorithm_metrics['diversity_score']
        
        # Clear cache for random trials
        self.distance_cache.clear()
        
        # Run random trials
        random_scores = []
        for trial in range(num_trials):
            random_indices = self.rng.sample(range(len(self.data_entries)), target_count)
            random_selection = [self.data_entries[i] for i in random_indices]
            random_metrics = self.calculate_diversity_metrics(random_selection)
            random_scores.append(random_metrics['diversity_score'])
        
        random_scores = np.array(random_scores)
        
        # Calculate p-value (one-tailed test: is algorithm better than random?)
        p_value = (1 + np.sum(random_scores >= algorithm_score)) / (1 + num_trials)
        
        # Calculate effect size (Cohen's d)
        effect_size = (algorithm_score - np.mean(random_scores)) / np.std(random_scores) if np.std(random_scores) > 0 else 0
        
        # Calculate confidence interval for random scores
        random_ci_lower = np.percentile(random_scores, 2.5)
        random_ci_upper = np.percentile(random_scores, 97.5)
        
        results = {
            "algorithm": algorithm_name,
            "algorithm_diversity_score": algorithm_score,
            "random_mean": float(np.mean(random_scores)),
            "random_std": float(np.std(random_scores)),
            "random_min": float(np.min(random_scores)),
            "random_max": float(np.max(random_scores)),
            "random_95_ci": (float(random_ci_lower), float(random_ci_upper)),
            "p_value": p_value,
            "effect_size_cohens_d": effect_size,
            "improvement_percent": (algorithm_score - np.mean(random_scores)) / np.mean(random_scores) * 100 if np.mean(random_scores) > 0 else 0,
            "significantly_better": p_value < 0.05
        }
        
        logger.info(f"\nStatistical results for {algorithm_name}:")
        logger.info(f"  Algorithm score: {algorithm_score:.4f}")
        logger.info(f"  Random mean: {results['random_mean']:.4f} ± {results['random_std']:.4f}")
        logger.info(f"  P-value: {p_value:.6f} {'(significant)' if p_value < 0.05 else '(not significant)'}")
        logger.info(f"  Effect size (Cohen's d): {effect_size:.3f}")
        logger.info(f"  Improvement over random: {results['improvement_percent']:.1f}%")
        
        return results


def categorize_single_car(car: dict):
    """Convert a car's attributes into key:value strings."""
    categorized = []
    for key, value in car.items():
        if isinstance(value, list):
            for item in value:
                categorized.append(f"{key}:{item}")
        else:
            categorized.append(f"{key}:{value}")
    return categorized


def categorize_car_data(json_file_path: Union[str, Path]):
    """Load and categorize car data from JSON."""
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"Could not find {json_path}")
    
    with json_path.open('r', encoding='utf-8') as f:
        cars = json.load(f)
    
    return [categorize_single_car(car) for car in cars]


def run_comprehensive_experiment(data_entries: List[List[str]], target_percent: float = 0.2):
    """Run comprehensive experiment with statistical validation."""
    config = ExperimentConfig(
        num_perm=128,
        l=32,
        random_seed=42,
        filter_keys=['id'],
        use_lsh=True,
        lsh_threshold=500,
        candidates_per_round=100
    )
    
    selector = ImprovedDiverseDataSelector(config)
    selector.load_data(data_entries)
    
    target_count = max(2, int(len(data_entries) * target_percent))
    target_count = min(target_count, 200)  # Cap at 200 for testing
    
    logger.info("\n" + "="*60)
    logger.info(f"COMPREHENSIVE EXPERIMENT")
    logger.info(f"Dataset size: {len(data_entries)}")
    logger.info(f"Target selection: {target_count} ({target_count/len(data_entries)*100:.1f}%)")
    logger.info("="*60)
    
    results = {}
    
    # 1. Compare all three methods
    logger.info("\n1. Method Comparison")
    results["method_comparison"] = selector.compare_methods(min(target_count, 50))
    
    # 2. Statistical validation against random baseline (using exact+chain)
    logger.info("\n2. Statistical Validation")
    results["statistical"] = selector.statistical_comparison_with_random(
        target_count, num_trials=100, use_lsh=False  # Use exact+chain as primary
    )
    
    # 3. Get final selection using exact + chain-aware (recommended approach)
    logger.info("\n3. Final Selection (Exact + Chain-Aware)")
    final_selection = selector.find_diverse_subset_exact(target_count, chain_aware=True)
    results["final_metrics"] = selector.calculate_diversity_metrics(final_selection)
    results["performance"] = {
        "distance_computations": selector.distance_computations,
        "chain_rejections": selector.chain_rejections,
    }
    
    return results, final_selection


def main():
    """Main function with comprehensive reporting."""
    json_file = "car_data.json"
    
    try:
        categorized_cars = categorize_car_data(json_file)
        
        logger.info(f"Loaded {len(categorized_cars)} cars")
        
        results, candidates = run_comprehensive_experiment(categorized_cars, target_percent=0.2)
        
        print("\n" + "="*60)
        print("EXPERIMENT RESULTS")
        print("="*60)
        
        # Method comparison
        if "method_comparison" in results:
            print("\nMethod Comparison:")
            comp = results["method_comparison"]
            
            print(f"\n  Exact (baseline):")
            print(f"    Diversity: {comp['exact']['diversity_score']:.4f}")
            print(f"    Computations: {comp['exact']['computations']:,}")
            
            print(f"\n  Exact + Chain-Aware:")
            print(f"    Diversity: {comp['exact_chain_aware']['diversity_score']:.4f}")
            print(f"    Computations: {comp['exact_chain_aware']['computations']:,}")
            print(f"    Chain rejections: {comp['exact_chain_aware']['chain_rejections']}")
            
            print(f"\n  LSH:")
            print(f"    Diversity: {comp['lsh']['diversity_score']:.4f}")
            print(f"    Computations: {comp['lsh']['computations']:,}")
            
            print(f"\n  Overlaps:")
            overlaps = comp['comparison']
            print(f"    Exact ↔ Chain-Aware: {overlaps['exact_vs_chain_overlap']*100:.1f}%")
            print(f"    Exact ↔ LSH: {overlaps['exact_vs_lsh_overlap']*100:.1f}%")
            print(f"    Chain-Aware ↔ LSH: {overlaps['chain_vs_lsh_overlap']*100:.1f}%")
        
        # Statistical significance
        if "statistical" in results:
            print("\nStatistical Significance (Exact+Chain vs Random):")
            stats = results["statistical"]
            print(f"  P-value: {stats['p_value']:.6f}")
            print(f"  Effect size (Cohen's d): {stats['effect_size_cohens_d']:.3f}")
            print(f"  Improvement over random: {stats['improvement_percent']:.1f}%")
            print(f"  Statistically significant: {stats['significantly_better']}")
        
        # Performance metrics
        if "performance" in results:
            print("\nFinal Performance:")
            perf = results["performance"]
            print(f"  Distance computations: {perf['distance_computations']:,}")
            print(f"  Chain rejections: {perf['chain_rejections']}")
        
        # Final diversity metrics
        if "final_metrics" in results:
            print("\nDiversity Metrics:")
            metrics = results["final_metrics"]
            print(f"  Mean pairwise distance: {metrics['mean_pairwise_distance']:.4f}")
            print(f"  Std deviation: {metrics['std_pairwise_distance']:.4f}")
            print(f"  Min distance: {metrics['min_pairwise_distance']:.4f}")
            print(f"  Max distance: {metrics['max_pairwise_distance']:.4f}")

        for a in candidates:
            print(a)
        #candidates[0]
        
    except FileNotFoundError:
        print(f"Error: Could not find '{json_file}'")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
