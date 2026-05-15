

Yes, basically — "unsafe items" are conceptually just ghost seeds: items that exert repulsive force on the selection process without appearing in the output.
Look at what a seed does in your farthest-first traversal: it sits in selected_ids so that the min_distances map keeps getting updated against it, pushing every subsequent pick away from it. The output happens to also include it — but that's a separate concern from its role in the geometry.
If you wanted to implement "unsafe" markers, the cleanest way is essentially:
python# Pretend these are already-selected items for distance purposes,
# but never emit them in selected_entries
unsafe_ids = {...}
selected_ids = set(unsafe_ids)         # used for repulsion
selected_entries = []                  # the actual output

# Then initialise min_distances against unsafe_ids
for entry_id, _ in self.data_entries:
    if entry_id not in selected_ids:
        min_distances[entry_id] = min(
            self.compute_distance(entry_id, u) for u in unsafe_ids
        )
That's it. The greedy loop doesn't need to change. Unsafe items pull min-distances down, candidates near them get filtered out by the farthest-first criterion, and they never get added to selected_entries.
A few subtleties worth noticing, though, before you call them "literally the same":
Repulsion is soft, not hard. A seed lowers a candidate's score but doesn't disqualify it. If everything else is even closer to other selections, a candidate near an unsafe item could still get picked — it's just downranked. If you want a hard exclusion zone ("nothing within distance ε of unsafe items, ever"), that's stronger than seed behaviour and you'd need an explicit filter, not just min-distance accounting.
Compare to chain risk, which is different. Chain risk is about local density in the LSH neighbourhood of the candidate — it asks "are too many of your neighbours already in the selected set?" It doesn't care about specific anchor items. Unsafe-as-seed is about avoiding specific points. The two are orthogonal: chain risk fights cluster collapse around emergent dense regions, unsafe-seeds fight proximity to known forbidden regions.
The first-pick problem. Your current random seed is picked from self.data_entries at random and then added to the output. If you switch to ghost-seed style with unsafe items, the very first emitted item should still be chosen as the farthest from the unsafe set, not random — otherwise your first pick ignores the constraint you set up.
So short answer: yes, the mental model "unsafe item = a seed that doesn't show up in the output" is right, and you can implement it with about five lines of changes. The thing that isn't equivalent is chain risk — that's solving a different problem (density), not avoidance of specific anchors.You said: Ok ok awesome.Ok ok awesome. So, my scenario is: I have an active item, so that makes it a seed. At any point I can turn those seeds to unsafe, I want a safety net around those unsafe seeds meaning when I re run the code it will always make sure nothing similar to those unsafe seeds are selected. But, I could also mark any item in ten data set as unsafe and I want to make sure those never get selected or nothing close to them gets selected. This technically reduces the pool of items that could be candidates but that's ok. Does your plan work?Show more14 MayClaude responded: The plan works, but with one important addition: you need to add an explicit safety threshold for the "nothing close gets selected" requirement.Validated plan with ghost seeds, flagged hard threshold necessityValidated plan with ghost seeds, flagged hard threshold necessityThe plan works, but with one important addition: you need to add an explicit safety threshold for the "nothing close gets selected" requirement. Pure ghost-seed repulsion is too soft — min-distance just downranks nearby candidates, it doesn't forbid them. If a candidate is close to an unsafe item but far from everything else, the soft repulsion alone could still let it through.
Here's the shape that handles your three categories cleanly:
pythonactive_ids = {...}    # seeds: in output, repel
unsafe_ids = {...}    # ghost seeds: NOT in output, repel + hard-block neighbours
SAFETY_RADIUS = 0.3   # tune this — anything closer than this to unsafe is forbidden

selected_ids = set(active_ids) | set(unsafe_ids)   # both repel via min_distance
selected_entries = [(aid, lookup[aid]) for aid in active_ids]  # only active is emitted

min_distances = {}
for entry_id, _ in self.data_entries:
    if entry_id in selected_ids:
        continue
    
    # Distance to the nearest already-anchored point (active or unsafe)
    d = min(self.compute_distance(entry_id, s) for s in selected_ids)
    
    # Hard block: too close to any unsafe item → drop from candidate pool entirely
    nearest_unsafe = min(self.compute_distance(entry_id, u) for u in unsafe_ids)
    if nearest_unsafe < SAFETY_RADIUS:
        continue   # forbidden, not just downranked
    
    min_distances[entry_id] = d
After this setup your existing greedy loop runs unchanged — it picks from min_distances, and the safety radius is enforced because forbidden items were never admitted to the candidate pool in the first place.
Three things to be aware of:
You only need to enforce the radius at init time, not inside the loop. Unsafe items don't move and you never add new ones mid-run, so a candidate that's far enough from all unsafe items at the start stays far enough forever. Future picks can only bring min_distance down by being closer than unsafe items were, which is fine.
Chain risk will count unsafe items as neighbours. Because they're in selected_ids, check_chain_risk will see them as "already selected." That's usually what you want — it makes the chain check sensitive to forbidden regions too — but if you ever notice it rejecting good candidates too aggressively, that's why. You can fix it by checking against active_ids only inside check_chain_risk rather than the full selected_ids.
Active-vs-unsafe conflict is a policy decision. If an active item happens to be close to an unsafe item, your code as written will keep it in the output (active wins, since you put it there explicitly) but its presence in selected_ids for repulsion is fine and consistent. If you'd rather flag or reject such conflicts at input time, do it before this setup. I wouldn't auto-resolve it silently.
The "reduces the candidate pool" framing you mentioned is exactly right — you're trading a smaller pool for hard safety guarantees, and given you've already accepted that tradeoff, this is the simplest way to get them.2 / 2You said: Ok ok awesome.Ok ok awesome. So, my scenario is: I have an active item, so that makes it a seed. At any point I can turn those seeds to unsafe, I want a safety net around those unsafe seeds meaning when I re run the code it will always make sure nothing similar to those unsafe seeds are selected. But, I could also mark any item in ten data set as unsafe and I want to make sure those never get selected or nothing close to them gets selected. This technically reduces the pool of items that could be candidates but that's ok. Does your plan work?Show more14 MayClaude responded: Looks like the same message came through twice — I gave you a full answer just above (ghost-seed setup + explicit SAFETY_RADIUS filter at init time, with notes…Evaluated safety filtering strategy for item selection systemEvaluated safety filtering strategy for item selection systemLooks like the same message came through twice — I gave you a full answer just above (ghost-seed setup + explicit SAFETY_RADIUS filter at init time, with notes on chain-risk interaction and active-vs-unsafe conflicts).
Did that response not load for you, or is there a specific piece you want me to go deeper on? Happy to drill into any of:

How to pick SAFETY_RADIUS for your data (e.g. based on the distribution of pairwise distances)
Whether to scope check_chain_risk against active_ids only vs. the full selected_ids
How "promoting" an active seed to unsafe should behave on re-run (just move the ID between sets, no other change needed)
A full patched version of find_diverse_subset_exact that takes both sets as arguments

Just point me at the bit you want.You said: Ah it sent twice so just ignore the second one.Ah it sent twice so just ignore the second one. Can you explain why just adding something to the seed set and marking is as unsafe, isn't enough to solve the core issue?14 MayClaude responded: Because farthest-first picks the maximum min_distance candidate — and "maximum" is relative to whatever else is in the pool, not an absolute floor.Dissected why soft repulsion through selection fails to enforce absolute safety thresholdsDissected why soft repulsion through selection fails to enforce absolute safety thresholdsBecause farthest-first picks the maximum min_distance candidate — and "maximum" is relative to whatever else is in the pool, not an absolute floor.
Putting an unsafe item U into selected_ids only guarantees this: every candidate's score gets capped by its distance to U. So a candidate close to U has a low score and is less attractive than alternatives. But "less attractive" isn't "rejected." If everything else in the pool happens to be even closer to some other selected item, the algorithm will happily pick the candidate near U because it's the best of a bad lot.
Concrete example. Say you've already picked active seeds A, B, C, D, and unsafe U is in selected_ids purely for repulsion. Two candidates remain:

c1: 0.05 from U, ≥ 0.7 from A/B/C/D → min_distance = 0.05
c2: 0.5 from U, but 0.04 from A → min_distance = 0.04

c1 wins. It's the farthest-first pick. And it's sitting right next to your unsafe item.
This gets worse as the selection grows. Farthest-first naturally produces picks with shrinking min_distance over time — by iteration 100, nothing is far from everything, and the algorithm is just picking the least-clustered option. The "unsafe" item is now just one of many anchors competing for influence, and its repulsion can easily lose to other constraints.
There's also a knock-on effect: once c1 (the unsafe-adjacent pick) is selected, it becomes a normal member of selected_ids. The algorithm has no memory that it was picked despite being near U. Future picks farthest from the selection set might cluster around c1 — and therefore around U — even though you never wanted that.
The hard threshold filter at init time fixes all of this by changing the question from "which candidate has the best score?" to "which candidate is in the legal pool, then which has the best score?" Two-stage. The unsafe constraint becomes a precondition for being a candidate at all, not just a factor in scoring. That's the only way to get an absolute guarantee rather than a soft preference.
Short version: min-distance repulsion is a tournament, and unsafe items just nudge the scoreboard. A hard radius filter is a bouncer at the door.You said: This is really helpful thank you.This is really helpful thank you. But I'm not sure I understand the concrete example you have me, can you dumb it down a little and talk me through?14 MayClaude responded: Sure, let me try again with a simpler picture.Devised picnic analogy to clarify algorithmic failure modeDevised picnic analogy to clarify algorithmic failure modeSure, let me try again with a simpler picture.
Imagine you're placing picnic blankets in a park. You already have:

Four blankets in the four corners of the park — these are your active items (friends you want to sit near).
One wasp nest in the middle of the park — this is your unsafe item (you don't want to sit near it).

The algorithm's rule for placing a new blanket is dead simple: "Find the spot where the nearest already-placed thing is as far away as possible." That's it. It just wants spots with breathing room.
Now you have two possible spots for your next blanket:
Spot c1: 1 metre from the wasp nest, 50 metres from every corner blanket.
Spot c2: 50 metres from the wasp nest, but only 0.5 metres from the blanket in the top-left corner.
The algorithm checks each spot's nearest neighbour:

For c1, the nearest thing is the wasp nest, 1 metre away.
For c2, the nearest thing is the corner blanket, 0.5 metres away.

Which has more breathing room from its nearest neighbour? c1 does — 1m > 0.5m. So the algorithm picks c1. And now your picnic blanket is 1 metre from a wasp nest.
Here's the problem in one sentence: the algorithm treated the wasp nest exactly like another blanket. It didn't know "wasp nest = bad, blanket = good." It just measured distance to the nearest thing and picked the spot with the most room.
That's what "soft repulsion" means in your code. By putting the unsafe item in selected_ids, you made the algorithm aware of it — it does count toward each candidate's score — but it counts the same way as any other selected item. There's no rule saying "stay extra far from this one."
The hard filter fixes this by changing the rule before the algorithm even runs. You walk around the park first and rope off a circle around the wasp nest. Then you let the algorithm pick the best spot, but only from spots outside the rope. Now c1 isn't even on the table — it never enters the competition. The algorithm is forced to pick c2 (or some other safe spot), and you can't end up next to wasps no matter what.
That's the whole distinction:

Soft (just adding to seed set): the unsafe item makes nearby spots look less attractive, but they're still in the running and can win if everything else looks worse.
Hard (radius filter at init): the unsafe item disqualifies nearby spots entirely, so they can't win no matter what.

Does that land better?You said: That's excellent thank you much!That's excellent thank you much! Furthest point first is always going to give diminishing returns right?14 MayClaude responded: Yes, mathematically guaranteed — it's not a quirk of your implementation, it's baked into the algorithm.Analyzed mathematical guarantees and practical implications of diminishing returnsAnalyzed mathematical guarantees and practical implications of diminishing returnsYes, mathematically guaranteed — it's not a quirk of your implementation, it's baked into the algorithm.
The pick-by-pick score (each new point's min_distance to the selected set at the moment it's chosen) is monotonically non-increasing. Each pick is at least as close to the existing selection as the previous pick was. The reason is simple: min_distance means "distance to your nearest selected neighbour." Adding more selected items can only bring your nearest neighbour closer (or leave it unchanged) — it can never push it further away. So as the selected set grows, the maximum available min_distance only drops.
In Jaccard space this is especially sharp because:

Distances are bounded by 1.0, so you have a hard ceiling on how diverse anything can be.
Your feature space is finite and discrete (cars have a limited combinatorial palette of attributes), so the supply of genuinely far-apart items runs out fast.

The shape you'll typically see if you plot pick-score vs. iteration:

First handful of picks: huge values, near 1.0. Totally disjoint feature sets — different segments, fuel types, body styles. Massive diversity gain per pick.
Middle stretch: scores drop steadily as the selected set starts covering the major regions of the space. Each pick is filling a gap.
Tail: scores collapse. By this point everything left in the pool shares meaningful overlap with something selected. You're picking "least bad of what's left" and your chain risk check has to work harder.

A few practical things this implies for your code:
The metric you'd want for detecting this is the score of the pick at the moment it was picked — not your final min_pairwise_distance over all selections. The latter is the worst case across the whole set; the former is the marginal diversity contribution of each pick. If you logged it (min_distances[best_candidate] right before you select), you'd get a clean falling curve, and the "knee" of that curve tells you roughly where additional picks stop earning their keep.
Once you have that curve, you can replace fixed target_count with an adaptive stop: keep picking until the next pick's score falls below some floor (say 0.3 in Jaccard space). That gives you "as many genuinely diverse items as the data supports, no more."
It also reframes your chain risk check nicely. It's not really fighting the algorithm — it's helping it gracefully handle the tail, where diminishing returns mean late picks naturally want to cluster. The check just enforces "if you're going to pick something not-very-far anyway, at least don't pick it right on top of an existing cluster."
So: yes, always diminishing, and that's a feature you can exploit rather than a bug you have to live with.You said: Can you explain how the chain safety mechanism works?Can you explain how the chain safety mechanism works?14 MayClaude responded: Good question — chain safety is solving a problem that pure farthest-first traversal can't see.Dissected chain risk algorithm, parameters, and local density detection mechanismDissected chain risk algorithm, parameters, and local density detection mechanismGood question — chain safety is solving a problem that pure farthest-first traversal can't see.
The problem it's solving
Recall the diminishing returns we just discussed: late in the selection, your remaining candidates all sit in similar leftover regions of the space. Farthest-first will dutifully pick the highest-min_distance one, but min_distance is a thin signal — it only measures distance to your single nearest selected item. So a candidate can have a respectable min_distance (it's not right on top of anything specific) while still being surrounded by lots of selected stuff at medium range.
That's how chains form. You pick A. Later you pick A′ — similar to A but not the nearest neighbour, so min_distance is fine. Later A″ — close to A and A′ but not directly on top of either. After ten picks you've quietly built a dense cluster in one region, with each individual pick looking justifiable in isolation. Farthest-first never notices, because it only ever looks at the single nearest neighbour.
How chain safety catches this
The chain check asks a different question: "In this candidate's local neighbourhood, how saturated is my selection already?" Local density, not nearest-neighbour distance.
Walking through check_chain_risk:

Take the candidate the algorithm is about to pick.
Use the LSH forest to find its 50 most similar items in the whole dataset (chain_risk_k). These are the candidate's "neighbours" — items that share lots of features with it.
Count how many of those 50 neighbours are already in selected_ids.
If that ratio is ≥ 10% (chain_risk_threshold), reject this candidate. It's in a region where you've already done plenty of selecting.

So the question isn't "is this candidate close to a selected item?" It's "is this candidate in a neighbourhood that's already over-represented in my selection?" That catches the cluster-building behaviour that min_distance can't.
What happens after a rejection
In the selection loop, candidates are sorted by min_distance descending — the farthest-first ordering. The loop walks down that list:
try top candidate → chain check fails → reject, try next
try second candidate → chain check fails → reject, try next
try third candidate → chain check passes → pick it
So you don't fall off a cliff — you're still picking the highest-min_distance candidate that also passes the density test. You're trading a tiny bit of nearest-neighbour distance for genuine novelty in the local neighbourhood.
The chain_risk_max_rejects=5 is a safety valve. If the first five candidates all fail the density check, the sixth gets accepted no matter what. This prevents the algorithm from starving in the late iterations when the tail of the selection is so clustered that nothing passes — you just admit defeat gracefully and take the next-best.
A concrete picture
Imagine you're selecting cars and you've already picked 80 of them. The farthest-first ranking now suggests a particular sporty hatchback as the next pick — its min_distance is 0.42 (the nearest selected car is a different sporty hatchback at Jaccard distance 0.42, which is OK but not great).
The chain check runs. It finds the 50 cars most similar to this hatchback in the whole dataset. Of those 50, 9 are already in your selection — they're all sporty hatchbacks of one stripe or another. 9/50 = 18%, well over the 10% threshold. Rejected.
Loop moves on. Next candidate is a vintage convertible with min_distance 0.40 — slightly lower than the hatchback. Its 50 LSH neighbours are mostly old convertibles, of which 2 are selected. 2/50 = 4%. Passes the check. That one gets picked instead.
You gave up 0.02 of min_distance, but you avoided adding a 10th car to a cluster of sporty hatchbacks. Over many iterations, this keeps the selection spread across many local regions rather than dense in a few.
Two key contrasts
Versus min_distance repulsion: min_distance looks at one neighbour (the nearest). Chain risk looks at a whole local neighbourhood. They catch different problems and complement each other — chain risk would be useless without min_distance providing the ordering, but min_distance alone misses cluster-building.
Versus the hard radius filter for unsafe items: the hard filter says "these specific regions are forbidden." Chain risk says "wherever I've already been a lot, ease off." The first is about external constraints; the second is about internal balance.
One thing worth flagging if you ever combine them: when unsafe items sit in selected_ids, they currently count toward chain risk. So a candidate near (but outside the radius of) an unsafe item could get rejected for chain risk too — because LSH sees unsafe items as "selected neighbours." Whether that's a feature or a bug depends on your goals. If you want unsafe items to enforce a hard exclusion zone but not influence chain risk dynamics, you'd pass active_ids (not selected_ids) into check_chain_risk.You said: Can you summarise how furthest point first works for me please?Can you summarise how furthest point first works for me please? When choosing a candidate it only factors in the min distance the current selected one? Not all the previous selections?14 MayClaude responded: Quick summary of the algorithm:Clarified algorithm mechanics and resolved misconception about distance calculationsClarified algorithm mechanics and resolved misconception about distance calculationsQuick summary of the algorithm:

Pick a seed — usually random, or you supply one.
For every candidate, compute its min_distance — defined as its distance to its nearest item in the selected set.
Pick the candidate with the maximum min_distance — the one whose nearest selected neighbour is the furthest away. Add it to the selected set.
Repeat until you have enough picks.

The phrase to remember is "min over selected, max over candidates." Each candidate summarises its relationship with the entire selected set into one number — the distance to its closest selected neighbour — and the algorithm picks whoever has the biggest such number.
To answer your specific question directly: it factors in all previous selections, not just the most recent one. But it summarises them into a single value per candidate ("how close are you to your nearest selected neighbour?") rather than tracking a separate distance for each historical pick.
The reason you might be looking at the code and seeing only one new distance computation per iteration is this clever bit in the update step:
pythonfor entry_id in min_distances:
    if entry_id not in selected_ids:
        dist_to_new = self.compute_distance(entry_id, best_candidate)
        min_distances[entry_id] = min(min_distances[entry_id], dist_to_new)
Each iteration only computes the distance from each candidate to the newest pick — but it compares that new distance against the running minimum, keeping whichever is smaller. So min_distances[entry_id] is always the distance to the nearest selected item across all picks so far — the value is maintained incrementally rather than recomputed from scratch.
It's the same answer as if you computed "distance to every selected item, take the min" each iteration — just much cheaper. With N candidates and K picks, the incremental version does N·K distance computations total; the naive recompute version would do N·K² for the same result.
Tiny concrete trace, three picks already in the selected set, asking about candidate c:

c to pick 1: 0.7
c to pick 2: 0.3
c to pick 3: 0.5

c's min_distance = 0.3 (its nearest selected item is pick 2). That's the single number used to compare c against every other candidate. Pick 1 and pick 3 are "there" in the sense that they were considered when this number was computed — but they don't bind, because pick 2 is closer and therefore dominates.
So all selections matter, but only the closest one to each candidate actually shows up in the score.You said: Ok tackling unsafe items - would one approach be to remove the item from the data set, plus the items x nearest neighbours, beige the selection mechanism, but …Ok tackling unsafe items - would one approach be to remove the item from the data set, plus the items x nearest neighbours, beige the selection mechanism, but not removing neighbours that are seeds?06:51Claude responded: Yes, this works — and it's actually the same fundamental idea as the radius filter I described earlier, just using k-nearest-neighbours topology instead of an …Evaluated preprocessing strategy for unsafe items using k-NN removal approachEvaluated preprocessing strategy for unsafe items using k-NN removal approachI'm considering the user's proposal to filter out unsafe items and their nearest neighbors before running the selection algorithm, while keeping any neighbors that are themselves seeds. The approach would identify unsafe items, find their x nearest neighbors via LSH, remove both from the candidate pool, but preserve neighbors that are active items. I need to think through whether this actually works and what the tradeoffs are.
The main advantage is conceptual clarity—filtering happens upfront before selection, so the selection algorithm doesn't need to know about unsafe items at all. It's simple to implement as a single preprocessing pass and works with any selection algorithm. The exception for seeds is smart because it preserves your active items even if they happen to be near unsafe ones. On the downside, defining "close" by k-nearest neighbors rather than a distance threshold is problematic—the k-th nearest neighbor in sparse regions of feature space could be quite far away, whereas in dense regions it might be very close.
This creates a fundamental difference from a radius-based approach: k-NN gives an item-count guarantee (exactly k neighbors excluded per unsafe item), while a fixed radius gives a uniform distance guarantee (nothing within distance R). There's also the issue that LSH neighbors are approximate—you might miss genuinely close items that a precise distance calculation would catch. And there's a subtle policy question: if you keep a seed because it's in your active set, but that seed is actually quite close to an unsafe item, you're accepting that risk. That's a deliberate choice, but worth being explicit about.
Now I'm thinking through the mechanics of how removed items interact with the LSH forest. If you remove unsafe items before building the forest, the forest never sees them. If you build the forest first and then remove items, you either rebuild the forest or filter them out at query time. The chain risk check looks at LSH neighbors of candidates and counts how many are in the selected set—if unsafe items are already removed, they won't appear in that count anyway, so the check still works correctly. The k-NN removal approach is actually quite similar to what's already in place with the LSH-based filtering. The radius approach offers a uniform distance guarantee—setting a threshold like 0.3 means nothing within that similarity margin survives—while the k-NN approach guarantees a fixed count of removals around each unsafe item. For their categorical car data in Jaccard space, the radius method feels more interpretable since "nothing more than X% similar to unsafe" is easier to reason about than "remove the 50 most similar," though the k-NN approach has its own advantages I'm still weighing.
The k-NN method avoids threshold selection, integrates naturally with LSH, and runs faster than computing distances to all items. A hybrid approach using LSH k-NN as a candidate set then filtering by distance threshold could give the best of both worlds. I should also flag a potential edge case in their approach: if the unsafe item itself ends up in the LSH forest, it'll be its own nearest neighbor, so they'd need to either filter it out or query for k+1 results and drop the self-match.
Since they mentioned rerunning the code, this is an iterative workflow where unsafe items accumulate over time. Each run takes the growing unsafe set, filters the dataset, and runs selection—their approach handles this cleanly since filtering just depends on which items are marked unsafe.
I'm realizing this is essentially the same core idea as the radius filter I described earlier, just using k-NN topology instead of explicit distance thresholds. Both shrink the candidate pool before selection runs. They've independently arrived at a slightly different version of the same insight, which is a good sign the approach is sound.Show lessDoneYes, this works — and it's actually the same fundamental idea as the radius filter I described earlier, just using k-nearest-neighbours topology instead of an explicit distance threshold. Both approaches shrink the candidate pool before the selection algorithm runs, which is exactly what you want.
Implementation sketch:
pythonunsafe_ids = {...}
active_ids = {...}    # your current seeds — keep these no matter what
X = 50                # neighbours-per-unsafe to exclude

forbidden = set(unsafe_ids)
for u in unsafe_ids:
    # +1 because LSH will return the item itself as nearest-to-self
    neighbours = self.lsh_forest.query(self.minhashes[u], k=X + 1)
    for n in neighbours:
        if n == u:
            continue
        if n in active_ids:
            continue   # your "seeds survive" rule
        forbidden.add(n)

filtered_entries = [(eid, data) for eid, data in self.data_entries
                    if eid not in forbidden]
# run selection on filtered_entries as normal
The "preserve seeds" exception is exactly right — if a seed happens to be in an unsafe neighbourhood, you put it there deliberately, so the unsafe filter shouldn't override that. Anything else gets purged.
The thing to be aware of is the semantic difference between the two approaches:
Radius filter (SAFETY_RADIUS = 0.3): "Nothing within Jaccard distance 0.3 of any unsafe item." Uniform safety guarantee, but the count of items removed depends on how dense your dataset is near each unsafe item — could be 5, could be 500.
k-NN removal (X = 50): "The 50 closest items to each unsafe item are removed." Uniform count guarantee, but the radius covered depends on local density — in a sparse region, the 50th nearest neighbour might be Jaccard distance 0.6 away; in a dense region, all 50 might be within 0.1.
Which is better depends on what you actually want to guarantee. If your worry is "I never want anything fundamentally similar to this unsafe item," radius is more interpretable — you set a similarity ceiling and that's the contract. If your worry is "remove a roughly fixed-size halo around each unsafe item regardless of how the data looks," k-NN is cleaner.
For your cars dataset (categorical Jaccard), I'd lean radius, because Jaccard distance has a meaningful real-world interpretation (proportion of features differing) and you can set it intentionally. But k-NN is faster and simpler — one LSH query per unsafe item, no full distance computations.
A pragmatic hybrid: use k-NN to fetch candidates cheaply, then filter those by a distance threshold to be safe. That way you get LSH's speed and the threshold's guarantee. Costs you one exact distance per LSH-returned neighbour, which is trivial.
One nice property of either filtering approach for your rerun workflow: it composes. Each time you re-run with a grown unsafe_ids set, the filter just gets stricter, the candidate pool shrinks, and the selection algorithm runs unchanged. The selection algorithm never has to know about unsafe items at all — it just sees a clean smaller dataset.



Yes, exactly the same way — just swap the LSH query for a distance check against SAFETY_RADIUS. The structure is identical, only the membership test changes:
pythonunsafe_ids = {...}
active_ids = {...}
SAFETY_RADIUS = 0.3

forbidden = set(unsafe_ids)
for u in unsafe_ids:
    for entry_id, _ in self.data_entries:
        if entry_id in active_ids:
            continue                                   # seeds survive
        if entry_id == u:
            continue
        if self.compute_distance(entry_id, u) < SAFETY_RADIUS:
            forbidden.add(entry_id)

filtered_entries = [(eid, data) for eid, data in self.data_entries
                    if eid not in forbidden]
# run selection on filtered_entries as normal
Same architecture as the k-NN version, same "seeds survive" exception, same downstream invariance — the selection algorithm has no idea unsafe items exist, it just sees a smaller dataset.
The trade-off compared to the k-NN approach is cost vs. guarantee:
Cost: this does |dataset| × |unsafe| exact distance computations up front. For your cars (thousands of items, presumably a handful of unsafe items at any time) that's trivial — a few thousand Jaccard computations, runs in milliseconds. If you had hundreds of unsafe items on a much larger dataset it could matter, but you're nowhere near that.
Guarantee: in exchange you get the exact semantic you actually want — "nothing within similarity distance R of any unsafe item" — instead of "the 50 most similar items happen to be removed." The radius is a contract; the k-NN count is an artifact of how the data clusters.
The hybrid I mentioned earlier is the practical sweet spot if you ever scale up:
pythonfor u in unsafe_ids:
    # Fast: LSH narrows the candidate set to "probably close" items
    candidates = self.lsh_forest.query(self.minhashes[u], k=200)
    for n in candidates:
        if n == u or n in active_ids:
            continue
        # Exact: verify with the real distance
        if self.compute_distance(n, u) < SAFETY_RADIUS:
            forbidden.add(n)
That uses LSH to skip the vast majority of items (most of the dataset isn't anywhere near any given unsafe item, so why compute), then exact distance to confirm the ones LSH flags as plausible. You keep the radius's clean semantic guarantee, and pay roughly |unsafe| × 200 distance computations instead of |unsafe| × |dataset|. For your current scale it's overkill, but the pattern's there when you need it.
One quiet benefit of doing this as preprocessing rather than as a check inside the selection loop: the selection algorithm stays completely untouched. No special-case code, no extra parameters, no conditional logic for unsafe items. The "filter → select" architecture is much easier to test, reason about, and rerun than weaving unsafe-handling through the greedy loop. Your code stays simple and the unsafe behaviour is one isolated function you can swap or tune independently.
