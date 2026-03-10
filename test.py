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
from dataclasses import dataclass, field
import math

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
    # Landscaper
    landscape_enabled: bool = False        # Enable landscape-aware soft scoring
    landscape_make_key: str = "make"       # Feature key for brand/make
    landscape_colour_key: str = "colour"   # Feature key for colour
    landscape_penalty_steepness: float = 4.0  # How sharply the penalty rises above quota (higher = harsher)

    def __post_init__(self):
        if self.filter_keys is None:
            self.filter_keys = ['id']

class Landscaper:
    """
    Landscape-aware quota manager for diverse subset selection.

    Architecture
    ------------
    Brand level  — HARD round-robin scheduling.
        At each iteration the selector asks which brand is most behind its
        quota (largest deficit as a fraction of its target).  Only candidates
        from that brand are considered for that slot.  This guarantees brand
        proportions are met and that within-brand diversity is maximised because
        the farthest-first traversal operates over a brand-filtered candidate set.

    Colour level — SOFT nudge within brand.
        Once the brand is chosen, candidates are scored by:
            effective_score = raw_distance × colour_multiplier
        where colour_multiplier = exp(-steepness × overshoot_ratio) for the
        candidate's colour-within-brand sub-quota.  Colours that are under their
        quota score at full distance; colours that have overshot are gently
        penalised.  The algorithm never hard-blocks a colour, so if only one
        colour exists for a brand it is always selected.

    Landscape data format
    ---------------------
        [
            {"ford":  1829482, "stats": {"yellow": 2.44, "pink": 0.32, "red": 5.65}},
            {"toyota": 3378747, "stats": {"yellow": 1.44, "pink": 0.61, "red": 8.65}},
        ]
    The top-level number is absolute market volume.  Stats values are the
    percentage of that brand's total represented by each colour.
    """

    def __init__(
        self,
        landscape_data: List[Dict],
        make_key: str = "make",
        colour_key: str = "colour",
        colour_penalty_steepness: float = 3.0,
    ):
        self.make_key = make_key
        self.colour_key = colour_key
        self.colour_penalty_steepness = colour_penalty_steepness

        # Parse landscape data
        self.brand_volumes: Dict[str, float] = {}
        self.colour_pcts: Dict[str, Dict[str, float]] = {}  # make -> colour -> pct

        total_volume = 0.0
        for entry in landscape_data:
            stats = entry.get("stats", {})
            brand_keys = [k for k in entry if k != "stats"]
            if not brand_keys:
                logger.warning(f"Landscape entry has no brand key: {entry}")
                continue
            brand = brand_keys[0].lower()
            volume = float(entry[brand_keys[0]])
            self.brand_volumes[brand] = volume
            self.colour_pcts[brand] = {c.lower(): pct for c, pct in stats.items()}
            total_volume += volume

        self.total_volume = total_volume
        self.brand_fractions: Dict[str, float] = {
            brand: vol / total_volume for brand, vol in self.brand_volumes.items()
        } if total_volume > 0 else {}

        # Filled in by set_target()
        self.target_count: int = 0
        self.brand_quota: Dict[str, float] = {}        # make -> float slot count
        self.colour_quota: Dict[str, Dict[str, float]] = {}  # make -> colour -> float slots

        logger.info(
            f"Landscaper initialised: {len(self.brand_volumes)} brands, "
            f"total volume={total_volume:,.0f}"
        )

    def set_target(self, target_count: int) -> None:
        """Pre-compute quota slot counts for a given selection target."""
        self.target_count = target_count
        self.brand_quota = {}
        self.colour_quota = {}

        for brand, frac in self.brand_fractions.items():
            brand_slots = frac * target_count
            self.brand_quota[brand] = brand_slots
            self.colour_quota[brand] = {
                colour: (pct / 100.0) * brand_slots
                for colour, pct in self.colour_pcts.get(brand, {}).items()
            }

        logger.info(
            f"Landscaper quotas set for target={target_count}: "
            + ", ".join(
                f"{b}={self.brand_quota[b]:.1f}" for b in list(self.brand_quota)[:5]
            )
            + ("..." if len(self.brand_quota) > 5 else "")
        )

    def next_brand(self, make_counts: Dict[str, int]) -> Optional[str]:
        """
        Round-robin brand scheduler.

        Returns the brand with the largest quota deficit.  Deficit is measured
        as (quota - current), i.e. absolute slots still owed.  This means larger
        brands (with more total slots) get priority when fractional deficits are
        equal, which produces the most natural fill order.
        Returns None if all brands are at or above quota.
        """
        best_brand = None
        best_deficit = -math.inf

        for brand, quota in self.brand_quota.items():
            if quota <= 0:
                continue
            current = make_counts.get(brand, 0)
            deficit = quota - current  # absolute slots still owed
            if deficit > best_deficit:
                best_deficit = deficit
                best_brand = brand

        return best_brand if best_deficit > 0 else None

    def colour_multiplier(
        self,
        make: str,
        colour: Optional[str],
        colour_counts: Dict[str, Dict[str, int]],
    ) -> float:
        """
        Soft colour-within-brand score multiplier.

        Returns 1.0 when the colour is under its sub-quota, decays smoothly
        toward 0 as overshoot grows.  Never returns exactly 0 so the algorithm
        always terminates even if one colour dominates the pool.
        """
        if colour is None:
            return 1.0

        quota = self.colour_quota.get(make, {}).get(colour, 0.0)

        if quota <= 0:
            # Colour has no real-world presence for this brand — penalise but don't block
            return 0.1

        current = float(colour_counts.get(make, {}).get(colour, 0))
        overshoot = current - quota
        if overshoot <= 0:
            return 1.0

        overshoot_ratio = overshoot / quota
        return math.exp(-self.colour_penalty_steepness * overshoot_ratio)

    def extract_facets(self, entry_data: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Extract (make, colour) from a raw entry's key:value list."""
        make = colour = None
        for item in entry_data:
            if ":" in item:
                k, v = item.split(":", 1)
                if k.strip() == self.make_key:
                    make = v.strip().lower()
                elif k.strip() == self.colour_key:
                    colour = v.strip().lower()
        return make, colour

    def landscape_report(
        self,
        selected_entries: List[Tuple[str, List[str]]],
    ) -> Dict:
        """
        Post-selection report comparing actual vs target brand/colour distribution.
        """
        make_counts: Dict[str, int] = defaultdict(int)
        colour_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        total = len(selected_entries)

        for _, entry_data in selected_entries:
            make, colour = self.extract_facets(entry_data)
            if make:
                make_counts[make] += 1
            if make and colour:
                colour_counts[make][colour] += 1

        report: Dict = {"brands": {}, "summary": {}}
        deviations = []

        for brand, target_frac in self.brand_fractions.items():
            actual_count = make_counts.get(brand, 0)
            actual_frac = actual_count / total if total > 0 else 0.0
            deviation = abs(actual_frac - target_frac)
            deviations.append(deviation)

            # Colour breakdown for this brand
            colour_detail = {}
            for colour, c_quota in self.colour_quota.get(brand, {}).items():
                c_actual = colour_counts[brand].get(colour, 0)
                colour_detail[colour] = {
                    "target_count": round(c_quota, 1),
                    "actual_count": c_actual,
                }

            report["brands"][brand] = {
                "target_pct": round(target_frac * 100, 2),
                "actual_pct": round(actual_frac * 100, 2),
                "target_count": round(self.brand_quota.get(brand, 0), 1),
                "actual_count": actual_count,
                "deviation_pct": round(deviation * 100, 2),
                "colours": colour_detail,
            }

        report["summary"] = {
            "mean_brand_deviation_pct": round(float(np.mean(deviations)) * 100, 2) if deviations else 0,
            "max_brand_deviation_pct": round(float(np.max(deviations)) * 100, 2) if deviations else 0,
            "brands_within_1pct": sum(1 for d in deviations if d < 0.01),
            "total_selected": total,
        }

        return report


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

        # Landscaper (optional)
        self.landscaper: Optional[Landscaper] = None

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

    def set_landscaper(self, landscaper: Landscaper) -> None:
        """Attach a Landscaper to this selector. Call before running selection."""
        self.landscaper = landscaper
        logger.info("Landscaper attached to selector.")

    def _build_brand_index(self) -> Dict[str, List[str]]:
        """
        Build a lookup of brand -> [entry_ids] from the loaded data.
        Used by the landscape brand scheduler to quickly find candidates
        belonging to a specific brand.
        """
        index: Dict[str, List[str]] = defaultdict(list)
        if self.landscaper is None:
            return index
        for entry_id, entry_data in self.data_entries:
            make, _ = self.landscaper.extract_facets(entry_data)
            if make:
                index[make].append(entry_id)
        return index

    def _init_facet_counts(self) -> Tuple[Dict[str, int], Dict]:
        """Initialise empty tracking dicts for make and colour counts."""
        return defaultdict(int), defaultdict(lambda: defaultdict(int))

    def _update_facet_counts(
        self,
        entry_data: List[str],
        make_counts: Dict[str, int],
        colour_counts: Dict,
    ) -> None:
        """Increment make and colour counts for a newly selected entry."""
        if self.landscaper is None:
            return
        make, colour = self.landscaper.extract_facets(entry_data)
        if make:
            make_counts[make] += 1
        if make and colour:
            colour_counts[make][colour] += 1

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
        Exact greedy diverse selection with optional landscape scheduling.

        Without landscaper
        ------------------
        Pure farthest-first traversal: at each step pick the unselected candidate
        with the largest minimum distance to the selected set.

        With landscaper (landscape_enabled=True)
        -----------------------------------------
        Brand level  — hard round-robin: ask the landscaper which brand is most
                       behind its quota; restrict candidates to that brand only.
        Colour level — soft nudge: within the brand-filtered candidate set, each
                       candidate's raw distance is multiplied by its colour
                       sub-quota multiplier before ranking.  Colours at or under
                       quota score at full distance; over-quota colours are gently
                       penalised.  Nothing is ever hard-blocked.

        Chain risk check applies after landscape filtering in both modes.
        """
        start_time = time.time()
        self.distance_computations = 0
        self.chain_rejections = 0
        self.distance_cache.clear()

        use_chain_check = (chain_aware and self.config.chain_risk_enabled
                          and self.forest_indexed)
        use_landscape = (self.landscaper is not None
                         and self.config.landscape_enabled)

        if use_chain_check:
            logger.info("Chain-aware exact selection active")
        if use_landscape:
            self.landscaper.set_target(target_count)
            brand_index = self._build_brand_index()
            logger.info(
                f"Landscape scheduling active: {len(brand_index)} brands indexed"
            )

        if target_count > len(self.data_entries):
            target_count = len(self.data_entries)

        # --- Seed ---
        seed_idx = self.rng.randint(0, len(self.data_entries) - 1)
        seed_id, seed_data = self.data_entries[seed_idx]

        selected_ids = {seed_id}
        selected_entries = [(seed_id, seed_data)]

        make_counts, colour_counts = self._init_facet_counts()
        self._update_facet_counts(seed_data, make_counts, colour_counts)

        # Initialise min-distance to all other entries
        min_distances: Dict[str, float] = {}
        for entry_id, _ in self.data_entries:
            if entry_id != seed_id:
                min_distances[entry_id] = self.compute_distance(entry_id, seed_id)

        entry_data_lookup = {eid: data for eid, data in self.data_entries}

        # --- Main loop ---
        for iteration in range(1, target_count):

            # Determine the candidate pool for this slot
            if use_landscape:
                scheduled_brand = self.landscaper.next_brand(make_counts)
            else:
                scheduled_brand = None

            if scheduled_brand is not None:
                # Brand-filtered pool: only candidates from the scheduled brand
                brand_pool = set(brand_index.get(scheduled_brand, []))
                pool = [
                    eid for eid in min_distances
                    if eid not in selected_ids and eid in brand_pool
                ]

                if not pool:
                    # Brand is exhausted in the dataset — fall back to global pool
                    logger.debug(
                        f"Iteration {iteration}: brand '{scheduled_brand}' exhausted, "
                        f"falling back to global pool"
                    )
                    pool = [eid for eid in min_distances if eid not in selected_ids]
            else:
                pool = [eid for eid in min_distances if eid not in selected_ids]

            if not pool:
                logger.warning(f"No candidates at iteration {iteration}")
                break

            # Score candidates: raw distance × colour multiplier (if landscape active)
            if use_landscape and scheduled_brand is not None:
                def score(eid: str) -> float:
                    raw = min_distances[eid]
                    _, colour = self.landscaper.extract_facets(entry_data_lookup[eid])
                    mult = self.landscaper.colour_multiplier(
                        scheduled_brand, colour, colour_counts
                    )
                    return raw * mult
            else:
                def score(eid: str) -> float:
                    return min_distances[eid]

            candidates_sorted = sorted(pool, key=score, reverse=True)

            # Walk sorted candidates; skip chain risks up to max_rejects
            best_candidate = None
            rejects = 0

            for cand_id in candidates_sorted:
                if use_chain_check and rejects < self.config.chain_risk_max_rejects:
                    if self.check_chain_risk(cand_id, selected_ids):
                        rejects += 1
                        continue
                best_candidate = cand_id
                break

            # Fallback — all rejected, take highest scorer anyway
            if best_candidate is None:
                best_candidate = candidates_sorted[0]

            selected_ids.add(best_candidate)
            selected_entries.append((best_candidate, entry_data_lookup[best_candidate]))
            self._update_facet_counts(
                entry_data_lookup[best_candidate], make_counts, colour_counts
            )

            # Update global min-distances (all unselected entries, not just pool)
            for entry_id in min_distances:
                if entry_id not in selected_ids:
                    dist_to_new = self.compute_distance(entry_id, best_candidate)
                    if dist_to_new < min_distances[entry_id]:
                        min_distances[entry_id] = dist_to_new

            if iteration % 50 == 0:
                logger.info(
                    f"Iteration {iteration}: {self.distance_computations} computations, "
                    f"{self.chain_rejections} chain rejections"
                )

        elapsed = time.time() - start_time
        logger.info(
            f"Exact selection: {elapsed:.2f}s, {self.distance_computations} computations, "
            f"{self.chain_rejections} chain rejections"
        )
        return selected_entries
    
    def find_diverse_subset_lsh(self, target_count: int) -> List[Tuple[str, List[str]]]:
        """
        LSH-accelerated diverse selection with optional landscape scheduling.

        Without landscaper
        ------------------
        Uses LSH to surface dissimilar candidates, then picks farthest-first.

        With landscaper (landscape_enabled=True)
        -----------------------------------------
        Brand level  — hard round-robin: restrict the LSH candidate pool to the
                       scheduled brand before distance ranking.
        Colour level — soft nudge: within the brand-filtered pool, multiply raw
                       distance by the colour sub-quota multiplier before ranking.

        Falls back to exact method for small datasets.
        """
        start_time = time.time()
        self.distance_computations = 0
        self.lsh_queries = 0
        self.chain_rejections = 0
        self.distance_cache.clear()

        if target_count > len(self.data_entries):
            target_count = len(self.data_entries)

        if len(self.data_entries) <= self.config.lsh_threshold:
            logger.info(
                f"Dataset size {len(self.data_entries)} <= {self.config.lsh_threshold}, "
                f"using exact method"
            )
            return self.find_diverse_subset_exact(target_count)

        use_landscape = (self.landscaper is not None
                         and self.config.landscape_enabled)

        if use_landscape:
            self.landscaper.set_target(target_count)
            brand_index = self._build_brand_index()
            logger.info(
                f"Landscape scheduling active in LSH selection: "
                f"{len(brand_index)} brands indexed"
            )

        # --- Seed ---
        seed_idx = self.rng.randint(0, len(self.data_entries) - 1)
        seed_id, seed_data = self.data_entries[seed_idx]

        selected_ids = {seed_id}
        selected_entries = [(seed_id, seed_data)]

        make_counts, colour_counts = self._init_facet_counts()
        self._update_facet_counts(seed_data, make_counts, colour_counts)

        entry_data_lookup = {eid: data for eid, data in self.data_entries}

        # active_candidates tracks min-distance for LSH-surfaced candidates
        active_candidates: Dict[str, float] = {}

        # --- Main loop ---
        for iteration in range(1, target_count):

            # Determine scheduled brand for this slot
            if use_landscape:
                scheduled_brand = self.landscaper.next_brand(make_counts)
                brand_pool = (
                    set(brand_index.get(scheduled_brand, []))
                    if scheduled_brand else None
                )
            else:
                scheduled_brand = None
                brand_pool = None

            # Refresh LSH candidate pool periodically or when running low
            if iteration % 10 == 1 or len(active_candidates) < 20:
                lsh_candidates = self.get_dissimilar_candidates_lsh(
                    selected_ids, k=self.config.candidates_per_round
                )
                for cand_id in lsh_candidates:
                    if cand_id not in active_candidates:
                        min_dist = min(
                            self.compute_distance(cand_id, sel_id)
                            for sel_id in selected_ids
                        )
                        active_candidates[cand_id] = min_dist

            # Filter active candidates to the scheduled brand (if landscape active)
            if brand_pool is not None:
                pool = {
                    eid: dist for eid, dist in active_candidates.items()
                    if eid in brand_pool
                }
                if not pool:
                    # Brand not in active set — fetch more LSH candidates
                    extra = self.get_dissimilar_candidates_lsh(
                        selected_ids, k=self.config.candidates_per_round * 2
                    )
                    for cand_id in extra:
                        if cand_id not in active_candidates:
                            min_dist = min(
                                self.compute_distance(cand_id, sel_id)
                                for sel_id in selected_ids
                            )
                            active_candidates[cand_id] = min_dist
                    pool = {
                        eid: dist for eid, dist in active_candidates.items()
                        if eid in brand_pool
                    }

                if not pool:
                    # Brand genuinely exhausted — fall back to global pool
                    logger.debug(
                        f"Iteration {iteration}: brand '{scheduled_brand}' exhausted "
                        f"in LSH pool, falling back to global"
                    )
                    pool = dict(active_candidates)
            else:
                pool = dict(active_candidates)

            if not pool:
                extra = self.get_dissimilar_candidates_lsh(
                    selected_ids, k=self.config.candidates_per_round * 2
                )
                for cand_id in extra:
                    if cand_id not in active_candidates:
                        min_dist = min(
                            self.compute_distance(cand_id, sel_id)
                            for sel_id in selected_ids
                        )
                        active_candidates[cand_id] = min_dist
                pool = dict(active_candidates)

            if not pool:
                logger.warning(f"No candidates at iteration {iteration}")
                break

            # Score: raw distance × colour multiplier
            def score_lsh(eid: str) -> float:
                raw = pool[eid]
                if use_landscape and scheduled_brand is not None:
                    _, colour = self.landscaper.extract_facets(entry_data_lookup[eid])
                    mult = self.landscaper.colour_multiplier(
                        scheduled_brand, colour, colour_counts
                    )
                    return raw * mult
                return raw

            sorted_pool = sorted(pool.keys(), key=score_lsh, reverse=True)

            # Walk sorted pool; skip chain risks
            best_candidate = None
            rejects = 0
            for cand_id in sorted_pool:
                if rejects >= self.config.chain_risk_max_rejects:
                    best_candidate = cand_id
                    break
                if self.check_chain_risk(cand_id, selected_ids):
                    rejects += 1
                    continue
                best_candidate = cand_id
                break

            if best_candidate is None:
                best_candidate = sorted_pool[0]

            best_data = entry_data_lookup[best_candidate]
            selected_ids.add(best_candidate)
            selected_entries.append((best_candidate, best_data))
            self._update_facet_counts(best_data, make_counts, colour_counts)

            if best_candidate in active_candidates:
                del active_candidates[best_candidate]

            # Update distances for remaining active candidates
            for cand_id in list(active_candidates.keys()):
                dist_to_new = self.compute_distance(cand_id, best_candidate)
                if dist_to_new < active_candidates[cand_id]:
                    active_candidates[cand_id] = dist_to_new
                if active_candidates[cand_id] < 0.1:
                    del active_candidates[cand_id]

            if iteration % 50 == 0:
                logger.info(
                    f"Iteration {iteration}: {self.distance_computations} computations, "
                    f"{self.lsh_queries} LSH queries, "
                    f"{len(active_candidates)} active candidates, "
                    f"{self.chain_rejections} chain rejections"
                )

        elapsed = time.time() - start_time
        logger.info(
            f"LSH selection: {elapsed:.2f}s, {self.distance_computations} computations, "
            f"{self.lsh_queries} LSH queries, {self.chain_rejections} chain rejections"
        )
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


def run_comprehensive_experiment(
    data_entries: List[List[str]],
    target_percent: float = 0.2,
    landscape_data: Optional[List[Dict]] = None,
):
    """Run comprehensive experiment with statistical validation."""
    config = ExperimentConfig(
        num_perm=128,
        l=32,
        random_seed=42,
        filter_keys=['id'],
        use_lsh=True,
        lsh_threshold=500,
        candidates_per_round=100,
        landscape_enabled=landscape_data is not None,
    )

    selector = ImprovedDiverseDataSelector(config)
    selector.load_data(data_entries)

    # Attach landscaper if landscape data is provided
    if landscape_data is not None:
        landscaper = Landscaper(landscape_data)
        selector.set_landscaper(landscaper)

    target_count = max(2, int(len(data_entries) * target_percent))
    target_count = min(target_count, 200)  # Cap at 200 for testing

    logger.info("\n" + "="*60)
    logger.info(f"COMPREHENSIVE EXPERIMENT")
    logger.info(f"Dataset size: {len(data_entries)}")
    logger.info(f"Target selection: {target_count} ({target_count/len(data_entries)*100:.1f}%)")
    logger.info(f"Landscape scoring: {'enabled' if landscape_data else 'disabled'}")
    logger.info("="*60)

    results = {}

    # 1. Compare all three methods
    logger.info("\n1. Method Comparison")
    results["method_comparison"] = selector.compare_methods(min(target_count, 50))

    # 2. Statistical validation against random baseline (using exact+chain)
    logger.info("\n2. Statistical Validation")
    results["statistical"] = selector.statistical_comparison_with_random(
        target_count, num_trials=100, use_lsh=False
    )

    # 3. Get final selection using exact + chain-aware + landscape (recommended)
    logger.info("\n3. Final Selection (Exact + Chain-Aware + Landscape)")
    final_selection = selector.find_diverse_subset_exact(target_count, chain_aware=True)
    results["final_metrics"] = selector.calculate_diversity_metrics(final_selection)
    results["performance"] = {
        "distance_computations": selector.distance_computations,
        "chain_rejections": selector.chain_rejections,
    }

    # 4. Landscape conformance report
    if landscape_data is not None and selector.landscaper is not None:
        results["landscape_report"] = selector.landscaper.landscape_report(final_selection)

    return results, final_selection, selector


def main():
    """Main function with comprehensive reporting."""
    json_file = "car_data.json"

    # ---------------------------------------------------------------------------
    # Example landscape data — replace with your real market metrics.
    # Format: list of dicts, each with one brand key (volume) and a "stats" dict
    # of colour percentages for that brand.
    # ---------------------------------------------------------------------------
    example_landscape_data = [
        {"ford":    1829482, "stats": {"yellow": 2.44, "pink": 0.32, "red": 5.65,
                                       "blue": 18.3, "white": 22.1, "black": 19.8,
                                       "grey": 16.4, "silver": 10.2, "green": 4.79}},
        {"toyota":  3378747, "stats": {"yellow": 1.44, "pink": 0.61, "red": 8.65,
                                       "blue": 15.2, "white": 28.4, "black": 17.6,
                                       "grey": 14.9, "silver": 9.8,  "green": 3.40}},
        {"bmw":      982341, "stats": {"yellow": 0.82, "pink": 0.18, "red": 6.10,
                                       "blue": 12.4, "white": 24.6, "black": 28.3,
                                       "grey": 18.1, "silver": 8.6,  "green": 0.92}},
        {"honda":   1543219, "stats": {"yellow": 1.90, "pink": 0.45, "red": 7.20,
                                       "blue": 16.8, "white": 25.3, "black": 16.4,
                                       "grey": 15.6, "silver": 11.2, "green": 5.15}},
    ]

    try:
        categorized_cars = categorize_car_data(json_file)

        logger.info(f"Loaded {len(categorized_cars)} cars")

        results, candidates, selector = run_comprehensive_experiment(
            categorized_cars,
            target_percent=0.2,
            landscape_data=example_landscape_data,   # pass None to disable
        )

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

        # Landscape conformance report
        if "landscape_report" in results:
            print("\nLandscape Conformance Report:")
            lr = results["landscape_report"]
            summary = lr["summary"]
            print(f"  Mean brand deviation: {summary['mean_brand_deviation_pct']:.2f}%")
            print(f"  Max brand deviation:  {summary['max_brand_deviation_pct']:.2f}%")
            print(f"  Brands within 1%:     {summary['brands_within_1pct']}")
            print(f"\n  {'Brand':<12} {'Target%':>8} {'Actual%':>8} {'Target#':>8} {'Actual#':>8} {'Dev%':>7}")
            print(f"  {'-'*57}")
            for brand, bd in sorted(lr["brands"].items(), key=lambda x: -x[1]["target_pct"]):
                print(
                    f"  {brand:<12} {bd['target_pct']:>7.2f}% {bd['actual_pct']:>7.2f}% "
                    f"{bd['target_count']:>7.1f}  {bd['actual_count']:>6}  {bd['deviation_pct']:>6.2f}%"
                )

        for a in candidates:
            print(a)

    except FileNotFoundError:
        print(f"Error: Could not find '{json_file}'")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
