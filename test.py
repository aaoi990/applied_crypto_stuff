Here's a breakdown of the four core concepts powering the diversity algorithm:
Jaccard similarity and distance measure how alike two sets of features are. For any two data entries, you take the size of their intersection (features they share) divided by the size of their union (all features between them). A score of 1.0 means identical; 0 means nothing in common. Jaccard distance is simply 1 - similarity, so 0 means identical and 1 means completely different. In this code, each car is converted into a set of key:value strings (e.g. "colour:red", "brand:BMW") and Jaccard distance is computed between any pair of those feature sets. The algorithm caches every result to avoid recomputing the same pair twice.
MinHash is a probabilistic technique for estimating Jaccard similarity cheaply — without comparing every feature directly. Instead of storing the full feature set, you generate a compact "signature" (a fixed-length array of hash values) that acts as a fingerprint. Two signatures can be compared in constant time, and the probability that any given hash position matches between two entries is mathematically equal to their Jaccard similarity. The code creates a 128-permutation MinHash for each car, which means the signature is 128 numbers long — giving a good balance of accuracy and speed.
LSH Forest (Locality Sensitive Hashing) is a data structure built on top of MinHash signatures. It groups similar entries into the same "buckets" so that nearest-neighbour queries are fast — O(log n) rather than O(n). Here it's used in a slightly inverted way: rather than finding the most similar items, the algorithm queries the LSH Forest to find items similar to already-selected entries, then excludes those from the candidate pool. What remains are the dissimilar candidates — the ones most worth considering next. This lets the algorithm avoid scanning the entire dataset on every iteration.
Farthest-Point First (FPF), also called greedy farthest-first traversal, is the core selection strategy. It works like this: start with a random seed entry, then at each step pick whichever unselected entry is farthest (in Jaccard distance) from the nearest point already in the selected set. The key data structure is a running min_distance value for each candidate — after each pick, you only need to update distances relative to the newly added point, not recompute everything from scratch. The result is a diverse subset where no two selected entries are unnecessarily close to each other. The chain_free_diversity.py version adds a "chain risk" check: before accepting the farthest-first candidate, it queries the LSH Forest to see how many of that candidate's neighbours are already selected — if too many are, it skips to the next-best option, preventing tight clusters from forming chains into the selection.
  
The diagram above shows how the four concepts chain together — click any node to explore it further. The key insight is that MinHash and LSH Forest are doing the heavy lifting of filtering so that Jaccard distance only needs to be computed for a small subset of promising candidates at each FPF step, rather than for every pair in the dataset.

How does the algorithm update min-distances after each selection?
After each entry is selected, the algorithm does an incremental update rather than recomputing everything from scratch. Here's the logic:
Each unselected candidate tracks a single value: its distance to the nearest point already in the selected set. When a new entry is added to the selected set, the algorithm loops over every remaining candidate and computes its distance to just that new entry. If that distance is smaller than the candidate's current recorded minimum, it updates it. Otherwise it leaves it alone.

for entry_id in min_distances:
    if entry_id not in selected_ids:
        dist_to_new = self.compute_distance(entry_id, best_candidate)
        min_distances[entry_id] = min(min_distances[entry_id], dist_to_new)

The reason this works efficiently is that the min-distance can only ever decrease as more points are added to the selected set — a new selection can introduce a closer neighbour, but can never make existing candidates farther away. So you never need to look back at previous selections; the current minimum already encodes all the history you need.
In the LSH version there's an additional pruning step: candidates whose min-distance drops below 0.1 (very similar to something already selected) are removed from the active candidate pool entirely, since they'd never win the farthest-point contest anyway:

if active_candidates[cand_id] < 0.1:
    del active_candidates[cand_id]

This means the active pool shrinks over time as the selected set fills in the "coverage" of the feature space, which keeps each iteration fast even as the selection grows.


"LSH Forest" is a slightly abstract structure, so let me build you a diagram that shows what's actually happening inside it.The best mental model for an LSH Forest is a set of random sorting games played on your data. Let me show you the structure first, then walk through exactly what happens during a query.
The core idea is this: you build l independent prefix trees (the "forest"), each one sorting all your entries by a different random projection of their MinHash signature. Two entries that land near each other in any of those trees are declared approximate neighbours. The more trees they co-locate in, the more confident you are they're actually similar.
 
 Each bucket label (like 00101…) is a binary prefix derived from the MinHash signature — entries whose signatures share the same prefix under that tree's random permutation get filed into the same bucket. The longer the prefix you match on, the tighter (more similar) the bucket.
When you call lsh_forest.query(minhash, k=50), it does exactly what the bottom row shows: hash the query signature to find its bucket in every tree simultaneously, collect all the entries that share that bucket across any tree, and return the union. The whole lookup is O(log n) per tree rather than O(n) for a brute-force scan — which is why querying 5,000 cars feels instant.
The l=32 parameter in the code means 32 independent trees. More trees means fewer misses (higher recall — similar items are less likely to fall in different buckets by bad luck in all 32), but more memory. The num_perm=128 controls how many hash functions define each signature, which trades accuracy against speed.
One subtle and important point about how this code uses the forest: it runs the query in reverse. Rather than asking "who is similar to my query?", it asks "who is similar to the already-selected entries?" — and then excludes those from the candidate pool. So the forest is being used as a dissimilarity filter, not a similarity finder, which is the clever twist at the heart of the algorithm.awesome again! As a side note, this method for dissimilarity. 

how novel is it? is it quirky or too specialised or scientific?

Great question — and the honest answer is: it's a genuinely clever inversion of a standard technique, but not a paradigm-shifting invention. Let me break down where it sits.Searched the webSearched the webHere's an honest placement of where this approach sits in the landscape:
The individual ingredients are well-established. LSH is a well-known technique in computer science, widely used for approximate nearest neighbour search. Wikipedia Farthest-point first (FPF) diversity selection is also a studied algorithm, particularly in cheminformatics — dissimilarity-based compound selection has been a recognised method for selecting structurally diverse subsets of chemical databases for decades, with the MaxMin algorithm (essentially FPF) being well regarded. PubMed And diversity maximization — finding a subset of k elements with maximum dissimilarity — is a fundamental problem with broad applications in data summarisation, web search, and recommender systems. ResearchGate
The specific inversion is the clever bit. Using LSH to exclude similar items rather than find them is not a standard textbook pattern. The canonical use of LSH is always framed as "find me neighbours of this query." Flipping it to "find me things that are not neighbours of my current selection, so I can focus the expensive distance computations there" — that's a pragmatic engineering insight rather than a novel theorem. It's the kind of thing that would appear as a paragraph in a systems paper ("we use LSH inversely to prune the candidate pool") rather than as its own publication.

What is the chain risk check and why does it help diversity?

The chain risk check is a guard against a subtle failure mode in farthest-point first selection. To understand why it exists, you need to see the failure first.
The chaining problem in FPF
Imagine your feature space has a long "corridor" of entries — cars that vary gradually along one dimension (say, engine size from 1.0L to 5.0L) but are all otherwise similar. FPF will happily march down that corridor step by step, because each new point is genuinely the farthest from the previous one. You end up with many selections clustered in one narrow region of feature space, just spread along a single axis. The rest of the space gets neglected.
This is chaining — the selected set forms a chain through a dense neighbourhood rather than spreading out across the whole space.
What the check does mechanically
Before accepting the farthest-point candidate, the algorithm queries the LSH Forest for that candidate's nearest neighbours. It then counts how many of those neighbours are already in the selected set:
pythonneighbours = self.lsh_forest.query(minhash, k=50)
selected_neighbours = sum(1 for n in neighbours if n in selected_ids)
overlap_ratio = selected_neighbours / len(neighbours)
is_risky = overlap_ratio >= self.config.chain_risk_threshold  # default 0.1
If 10% or more of the candidate's neighbourhood is already selected, the candidate is flagged as a chain risk and skipped. The algorithm then tries the next-best candidate instead. It will only do this up to chain_risk_max_rejects times (default 5) before accepting anyway — so it never gets stuck.
Why 10% is a meaningful threshold
If a candidate has 50 LSH neighbours and 5 of them are already selected, that means the selected set is already well-represented in that pocket of feature space. Adding another point there gives you diminishing returns on diversity — you're deepening coverage in one area at the expense of breadth elsewhere.
Step through that to see the failure mode and the fix side by side.
Why this is a real problem for FPF specifically
FPF is provably a 2-approximation to the optimal diverse subset — meaning it's never worse than half as diverse as the theoretical best. But that guarantee is about the minimum pairwise distance, not the distribution across the space. A chain satisfies the guarantee (each step is genuinely far from the previous one) while still producing a lopsided selection.
The trade-off
The chain check is not free. It costs one LSH Forest query per candidate evaluated, and it can occasionally reject a genuinely good candidate if it happens to have many selected neighbours by coincidence rather than because it's truly redundant. That's why chain_risk_max_rejects = 5 exists — after 5 rejections the algorithm accepts the best remaining option anyway, preventing it from spiralling into endless rejections in dense regions. It's a pragmatic heuristic on top of a theoretically sound base algorithm, not a theoretically guaranteed improvement itself.How does farthest-first pick the next entry to add?21:14FPF's selection rule is beautifully simple: at every step, pick whichever unselected entry is farthest from its nearest selected neighbour.
That phrase "nearest selected neighbour" is the key. You're not measuring distance to the whole selected set — you're measuring each candidate's distance to the closest thing already selected. Then you pick the candidate where that closest-neighbour distance is largest. In other words: find the point that is least well-covered by the existing selection.
Here's the exact logic from the code:

python# Each candidate tracks its distance to the nearest selected point
min_distances[entry_id] = min(min_distances[entry_id], dist_to_new)

# Pick the candidate with the largest min-distance
best_candidate = max(
    (eid for eid in min_distances if eid not in selected_ids),
    key=lambda x: min_distances[x]
)
tThe thing worth stepping through carefully is what happens after each selection. After picking F, every remaining point checks: "am I now closer to F than I am to A?" If yes, F becomes its nearest selected neighbour and the distance to F becomes its new min-distance. The line re-points. This incremental update is what makes FPF efficient — you never recompute everything from scratch, you just fold in the new point.
The geometric intuition
What FPF is really doing is placing selections to maximise the coverage radius — the maximum distance from any unselected point to its nearest selected point. Each step shrinks the worst uncovered gap in feature space. After k selections, no point is more than some distance d from a selected point, and that d is as small as possible given k selections.
The one weakness to keep in mind
Because it always picks the single farthest point, FPF is greedy and slightly myopic. It commits to each choice permanently. If the first random seed happens to land in a dense cluster, subsequent picks will spend several iterations escaping that cluster before they can spread out — which is exactly the scenario the chain risk check is designed to interrupt.
