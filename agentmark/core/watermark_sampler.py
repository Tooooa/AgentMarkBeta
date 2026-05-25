"""
Watermark Sampler Module
Responsibility: Contains all algorithms related to behavior sampling
"""

import random
import json
import math
import torch
import hmac
import hashlib
import numpy as np
import os
import json


# ==============================================================================
# ================ Contextual Key Generation ================
# ==============================================================================

def generate_contextual_key(history_responses, num_bytes=32):
    """
    Generate a deterministic key based on history responses (context).
    
    Args:
        history_responses (list): A list of past behavior description strings.
        num_bytes (int): Number of bytes for the generated key (default 32, corresponding to SHA-256).

    Returns:
        bytes: The generated key.
        
    Example:
        >>> history = ["User liked the video", "User collected the video"]
        >>> key = generate_contextual_key(history)
        >>> len(key)
        32
    """
    if not history_responses:
        # Cold start: If history is empty, use a fixed initial string
        context_string = "INITIAL_CONTEXT_FOR_AGENT_WATERMARK"
    else:
        # Use simple strategy: use the most recent response as context
        # Here we use the last response, can be extended to concatenation of multiple responses
        context_string = history_responses[-1]
        
    # Use SHA-256 hash function to convert context string to a fixed-length key
    hasher = hashlib.sha256()
    hasher.update(context_string.encode('utf-8'))
    return hasher.digest()[:num_bytes]


def derive_contextual_watermark_key(context_used, watermark_key=None, num_bytes=32):
    """
    Derive the per-step DRBG key.

    If watermark_key is provided, bind the public context to that owner secret.
    If omitted, preserve the legacy experiment behavior that derives the key
    from context alone.
    """
    context_bytes = (context_used or "").encode("utf-8")
    if watermark_key is None:
        return generate_contextual_key([context_used], num_bytes=num_bytes)
    if isinstance(watermark_key, str):
        watermark_key = watermark_key.encode("utf-8")
    return hmac.new(watermark_key, context_bytes, hashlib.sha512).digest()[:num_bytes]


# ==============================================================================
# ================ Differential Scheme Watermark Engine ================
# ==============================================================================

# ---- Legacy DRBG (Kept for backward compatibility with differential mode) ----
class DRBG_Legacy:
    """
    Old Counter-mode DRBG.
    """
    def __init__(self, key, nonce):
        self.key = key
        self.nonce = nonce
        self.counter = 0

    def generate_random_bits(self, n):
        message = self.nonce + self.counter.to_bytes(4, 'big')
        hmac_sha512 = hmac.new(self.key, message, hashlib.sha512).digest()
        self.counter += 1
        
        bits = ''.join(format(byte, '08b') for byte in hmac_sha512)
        return bits[:n]

    def generate_random(self, n):
        # Generate a floating point number in (0,1) from bit string
        random_bits = self.generate_random_bits(n)
        random_int = int(random_bits, 2)
        random_float = random_int / (2**n)
        return random_float


# ---- Meteor-style DRBG (New Default) ----
class DRBG:
    """
    Deterministic Random Bit Generator (DRBG), Meteor style.
    Based on HMAC-SHA512 reseed mode.
    Reference: Kaptchuk et al., "Meteor: Cryptographically Secure Steganography 
    for Realistic Distributions," CCS 2021.
    """
    def __init__(self, key: bytes, seed: bytes):
        self.key = key
        self.val = b'\x01' * 64
        self.reseed(seed)
        self.byte_index = 0
        self.bit_index = 0

    def hmac(self, key: bytes, val: bytes) -> bytes:
        return hmac.new(key, val, hashlib.sha512).digest()

    def reseed(self, data: bytes = b'') -> None:
        self.key = self.hmac(self.key, self.val + b'\x00' + data)
        self.val = self.hmac(self.key, self.val)
        if data:
            self.key = self.hmac(self.key, self.val + b'\x01' + data)
            self.val = self.hmac(self.key, self.val)

    def generate_bits(self, n: int) -> np.ndarray:
        """Generate n random bits."""
        xs = np.zeros(n, dtype=bool)
        for i in range(n):
            xs[i] = (self.val[self.byte_index] >> (7 - self.bit_index)) & 1
            self.bit_index += 1
            if self.bit_index >= 8:
                self.bit_index = 0
                self.byte_index += 1
            if self.byte_index >= 8:
                self.byte_index = 0
                self.val = self.hmac(self.key, self.val)
        self.reseed()
        return xs

    def generate_random(self, n: int = 52) -> float:
        """Generate a random float in [0, 1)."""
        xs = self.generate_bits(n)
        decimal_value = 0
        for bit in xs:
            decimal_value = (decimal_value << 1) | int(bit)
        max_value = (1 << n)
        return decimal_value / max_value


# ---- Probability Distribution Wrapper (For RankStego) ----
class Dist:
    """
    Encapsulates a probability distribution for RankStego.
    """
    def __init__(self, probs: torch.Tensor, indices: torch.Tensor = None):
        self.probs = probs
        self.device = probs.device
        if indices is None:
            self.indices = torch.arange(0, len(probs), device=self.device)
        else:
            self.indices = indices.to(self.device).to(torch.long)

    def __len__(self):
        return len(self.probs)

    def __getitem__(self, idx):
        return self.indices[idx], self.probs[idx]

    def sort(self, descending: bool = True) -> "Dist":
        probs, sorted_indices = torch.sort(self.probs, descending=descending)
        indices = self.indices[sorted_indices]
        return Dist(probs, indices)

    def get_max(self):
        max_idx = torch.argmax(self.probs)
        return self[max_idx]

    def get_sort(self, descending: bool = True):
        probs, sorted_indices = torch.sort(self.probs, descending=descending)
        indices = self.indices[sorted_indices]
        return probs, indices

# Uniform cyclic shift encoder (selects an item within the selected "bin" based on secret info)
# Standard version - Consistent with Artifacts implementation
def uni_cyclic_shift_enc(bit_stream, n, PRG, precision=52):
    """
    Cyclic shift uniform steganography encoder (Artifacts standard version)
    
    Args:
        bit_stream (str): Bit stream to embed
        n (int): Bin size
        PRG: Pseudo-random generator
        precision (int): Precision parameter
        
    Returns:
        tuple: (selected index, embedded bit string)
    """
    if n == 1:
        PRG.generate_random(n=precision)
        return 0, ''
    
    ptr = PRG.generate_random(n=precision)
    R = math.floor(ptr * n)
    
    k = math.floor(math.log2(n))
    t = n - 2**k
    
    # Check if bit stream is sufficient
    if len(bit_stream) < k:
        # Insufficient bit stream, select randomly but consume PRG to maintain synchronization
        return R, ''
    
    bits = bit_stream[:k]
    
    # Check if an extra bit is needed
    if len(bit_stream) < k + 1:
        bits_res = '0'  # Default value
    else:
        bits_res = bit_stream[k]
    
    idx_sort = lsb_bits2int([int(b) for b in bits])
    
    if idx_sort < 2**k - t:
        return (idx_sort + R) % n, bits
    else:
        return (2 * (idx_sort - (2**k - t)) + (2**k - t) + R + int(bits_res)) % n, bits + bits_res

# Differential recombination module (Core innovation: horizontal slicing)
# V2: Use stable sort to handle equal probabilities
# ---- Rank Scheme Core Algorithms ----

def BinEncStep(m: str, dist: Dist, rt: float):
    """
    Binary encoding step: embeds 1 bit into a 2-item distribution.
    If message bit is '1' and random offset falls in the max prob item, no embed (0 bits);
    otherwise select the minor item and embed 1 bit.
    """
    dist_sum = dist.probs.sum()
    rt_m = (rt * dist_sum + 0.5 * dist_sum * int(m)) % dist_sum
    max_indice, max_prob = dist.get_max()
    
    # Identify the other index
    if max_indice.item() == dist.indices[0].item():
        min_indice = dist.indices[1]
    else:
        min_indice = dist.indices[0]
        
    if rt_m < max_prob.item():
        return max_indice.view(1, 1), 0
    else:
        return min_indice.view(1, 1), 1


def RankEncStep(M: str, dist: Dist, PRG: DRBG):
    """
    Recursive binary splitting for ranked distribution.
    Embeds bits from M at each level.
    Returns: (selected index, total bits embedded)
    """
    dist = dist.sort()
    msg_idx = 0
    # Sync PRG calls: total steps = ceil(log2(N))
    rt_sync = math.ceil(math.log2(len(dist)))
    
    while len(dist) > 1:
        high_prob = dist.probs[::2].sum()
        low_prob = dist.probs[1::2].sum()
        dist_bin = Dist(torch.tensor([high_prob, low_prob], device=dist.probs.device))
        
        if msg_idx >= len(M):
            # Fallback: if message ends, don't embed but continue sync
            m = '0' 
            # In RankStego, if we run out of bits, we should probably stop embedding.
            # But the loop must finish to select a token.
            # However, the source code expects M to be long enough.
            # We'll return what we have.
            break
            
        m = M[msg_idx]
        rt = PRG.generate_random(n=52)
        rt_sync -= 1
        
        T_group, n_bits = BinEncStep(m, dist_bin, rt)
        msg_idx += n_bits
        
        if T_group.item() == 0:
            dist = Dist(dist.probs[::2], dist.indices[::2])
        else:
            dist = Dist(dist.probs[1::2], dist.indices[1::2])
            
    # Consume remaining PRG calls for sync
    for _ in range(rt_sync):
        PRG.generate_random(n=52)
        
    T = dist.indices[0].view(1, 1)
    return T, msg_idx


def BinDecStep(T: torch.Tensor, sorted_indices: torch.Tensor, rt: float) -> str:
    """
    Binary decoding step: extracts bit based on rank position.
    """
    if T.item() == sorted_indices[0].item():
        return ''
    else:
        return '1' if rt < 0.5 else '0'


def RankDecStep(T: torch.Tensor, sorted_indices: torch.Tensor, PRG: DRBG) -> str:
    """
    Weakly asymmetric decoding: only needs the sorted order.
    Extracts bit sequence backwards from the token's rank.
    """
    decoded_bits = ''
    rank_matches = (sorted_indices == T.item()).nonzero(as_tuple=True)[0]
    if len(rank_matches) == 0:
        return ''
    rank = rank_matches.item()
    
    rt_sync = math.ceil(math.log2(len(sorted_indices)))
    
    # Generate exactly the same per-level random numbers as RankEncStep.
    # Previously this function accidentally generated the sequence twice and
    # decoded from the second batch, shifting the PRG stream and reducing
    # recovered-bit accuracy to chance level.
    rts = [PRG.generate_random(n=52) for _ in range(rt_sync)]
    current_level = 0
    while rank != 0:
        rt = rts[current_level]
        if rank % 2 == 1:
            bit = '1' if rt < 0.5 else '0'
            decoded_bits += bit
        rank = rank // 2
        current_level += 1
        
    return decoded_bits


def differential_based_recombination(prob, indices):
    bins = []
    
    # ========================== Use Stable Sort ==========================
    # torch.argsort returns an index tensor that sorts the input tensor.
    # stable=True ensures that when values in prob are equal, the corresponding indices maintain their original order.
    # This is key to guaranteeing encoding/decoding synchronization!
    # [FIX] Round probabilities to avoid floating point noise changing the order of "equal" values
    prob_rounded = torch.round(prob * 1e8) / 1e8
    sorted_order_indices = torch.argsort(prob_rounded, stable=True, descending=False)
    
    # Use this deterministic order to rearrange prob and indices
    prob = prob[sorted_order_indices]
    indices = indices[sorted_order_indices]
    # ==================================================================

    mask = prob > 0
    prob_nonzero = prob[mask]
    indices_nonzero = indices[mask]
 
    diff = torch.cat((prob_nonzero[:1], torch.diff(prob_nonzero, n=1)))
    n = len(prob_nonzero)

    weights = torch.arange(n, 0, -1, device = prob.device) 
    diff_positive = diff > 0

    prob_new = diff[diff_positive] * weights[diff_positive] 
    bins = torch.arange(n, device = prob.device)[diff_positive]

    return indices_nonzero, bins, prob_new

# Differential Encoder (Engine Assembly)
def differential_based_encoder(prob, indices, bit_stream, bit_index, PRG, precision = 52, **kwargs):
    indices_nonzero, bins, prob_new = differential_based_recombination(prob, indices)
    if prob_new.sum() == 0: # Avoid division by zero
        # If all probabilities are equal, select one randomly
        random_idx = int(PRG.generate_random(precision) * len(indices))
        return indices[random_idx].view(1,1), 0

    prob_new = prob_new/prob_new.sum()

    random_p = PRG.generate_random(n = precision)
    cdf = torch.cumsum(prob_new, dim=0)
    bin_indice_idx = torch.searchsorted(cdf, random_p).item()
    
    selected_bin_start_index = bins[bin_indice_idx]
    bin_content = indices_nonzero[selected_bin_start_index:]

    idx, bits = uni_cyclic_shift_enc(bit_stream=bit_stream[bit_index:], n = len(bin_content), PRG = PRG, precision=precision)
    
    num = len(bits)
    if os.getenv("AGENTMARK_DEBUG_SAMPLER"):
        print(f"[agentmark:encoder] bin_size={len(bin_content)}, k={math.floor(math.log2(len(bin_content))) if len(bin_content) > 1 else 0}, bits_embedded='{bits}', num={num}")
    prev = bin_content[idx].view(1,1)

    return prev, num


# ==============================================================================
# ================ Basic Sampling Algorithms ================
# ==============================================================================

def sample_behavior(probabilities, seed=None, round_num=0, strategy="weighted", temperature=1.0):
    """
    Select a behavior from the list based on probabilities (No Watermark Version)
    
    Args:
        probabilities (dict): Dictionary of behaviors and their corresponding probabilities
        seed (int, optional): Random seed to ensure reproducibility
        round_num (int, optional): Current round number to introduce variation based on fixed seed
        strategy (str): Sampling strategy, options:
            - "weighted": Weighted random sampling (original probability distribution)
            - "greedy": Greedy selection (select the one with highest probability)
            - "temperature": Temperature sampling (adjust probability distribution using temperature parameter)
        temperature (float): Temperature parameter, only used when strategy="temperature"
            - temperature < 1.0: More inclined towards high probability actions
            - temperature = 1.0: Equivalent to weighted sampling
            - temperature > 1.0: More uniform distribution
        
    Returns:
        str: Selected behavior
        
    Example:
        >>> probs = {"Like": 0.3, "Collect": 0.2, "Repost": 0.5}
        >>> sample_behavior(probs, seed=42, round_num=1, strategy="greedy")
        'Repost'  # Always selects the one with highest probability
    """
    # Set random seed
    if seed is not None:
        combined_seed = seed + round_num
        random.seed(combined_seed)
    
    # Get behavior list and corresponding probability list
    behaviors = list(probabilities.keys())
    probs = list(probabilities.values())
    
    # Ensure probabilities sum to 1
    total = sum(probs)
    if total != 1.0:
        probs = [p/total for p in probs]
    
    if strategy == "greedy":
        # Greedy strategy: Select the action with highest probability (similar to official ALFWorld eval mode)
        max_idx = probs.index(max(probs))
        selected_behavior = behaviors[max_idx]
    
    elif strategy == "temperature":
        # Temperature sampling: Adjust the "sharpness" of the probability distribution
        # Lower temperature means more inclination towards high probability actions
        if temperature <= 0:
            raise ValueError("Temperature must be positive")
        
        # Apply temperature scaling
        scaled_probs = [p ** (1.0 / temperature) for p in probs]
        total_scaled = sum(scaled_probs)
        scaled_probs = [p / total_scaled for p in scaled_probs]
        
        # Use scaled probabilities for weighted sampling
        selected_behavior = random.choices(behaviors, weights=scaled_probs, k=1)[0]
    
    else:  # "weighted" or default
        # Weighted random sampling: Sample according to original probability distribution
        selected_behavior = random.choices(behaviors, weights=probs, k=1)[0]
    
    return selected_behavior


# ==============================================================================
# ================ Traditional Watermark Sampling Algorithms ================
# ==============================================================================

def sample_behavior_watermark(probabilities, seed=None, round_num=0, prob_bias=0.5, ratio=0.5, BEHAVIOR_TYPES=[]):
    """
    Randomly select a behavior from list based on probabilities, adding probability bias to some behaviors (Old Probability Bias Watermark)
    
    Args:
        probabilities (dict): Dictionary of behaviors and their corresponding probabilities
        seed (int, optional): Random seed to ensure reproducibility
        round_num (int, optional): Current round number to introduce variation based on fixed seed
        prob_bias (float, optional): Probability bias to adjust probability
        ratio (float, optional): Proportion of behaviors to bias, 0-1, controls how many BEHAVIOR_TYPES get prob_bias added
        BEHAVIOR_TYPES (list, optional): List of behavior types

    Returns:
        tuple: (Selected behavior, List of behaviors with added probability bias)
        
    Example:
        >>> probs = {"Like": 0.3, "Collect": 0.2, "Repost": 0.5}
        >>> behavior, biased_list = sample_behavior_watermark(probs, seed=42, round_num=1, prob_bias=0.5, ratio=0.5, BEHAVIOR_TYPES=['Like', 'Collect', 'Repost'])
        >>> print(f"Selected: {behavior}, Biased: {biased_list}")
    """
    # Number of behaviors
    behavior_num = len(BEHAVIOR_TYPES)
    
    # Set random seed
    if seed is not None:
        # Combine seed and round number to create new seed
        combined_seed = seed + round_num
        random.seed(combined_seed)
    
    # Partition behaviors needing bias based on combined_seed and ratio
    # Calculate count of behaviors to bias
    biased_count = int(behavior_num * ratio)
    # Randomly select behaviors to bias
    add_logits_behavior_list = random.sample(BEHAVIOR_TYPES, biased_count)
    
    # Get behavior list and corresponding probability list
    behaviors = list(probabilities.keys())
    probs = list(probabilities.values())
    
    # Add probability bias to selected behaviors
    modified_probs = []
    for behavior, prob in zip(behaviors, probs):
        if behavior in add_logits_behavior_list:
            modified_probs.append(prob + prob_bias)
        else:
            modified_probs.append(prob)
    
    # Ensure probabilities sum to 1
    total = sum(modified_probs)
    if total != 1.0:
        modified_probs = [p/total for p in modified_probs]
    
    # Use random.choices for weighted random selection
    selected_behavior_watermark = random.choices(behaviors, weights=modified_probs, k=1)[0]
    
    return selected_behavior_watermark, add_logits_behavior_list


def sample_behavior_watermark_uncertainty(probabilities, seed=None, round_num=0, prob_bias=0.5, ratio=0.5, BEHAVIOR_TYPES=[], uncertainty_threshold=0.5):
    """
    Randomly select a behavior based on probabilities, adding bias to some behaviors, and evaluate behavior uncertainty.
    
    Args:
        probabilities (dict): Dictionary of behaviors and their corresponding probabilities
        seed (int, optional): Random seed to ensure reproducibility
        round_num (int, optional): Current round number to introduce variation based on fixed seed
        prob_bias (float, optional): Probability bias to adjust probability
        ratio (float, optional): Proportion of behaviors to bias, 0-1, controls how many BEHAVIOR_TYPES get prob_bias added
        BEHAVIOR_TYPES (list, optional): List of behavior types
        uncertainty_threshold (float, optional): Uncertainty threshold, behaviors above this are considered unstable

    Returns:
        tuple: (Selected behavior, List of behaviors with added probability bias, Whether watermark is applied, Uncertainty score)
        
    Example:
        >>> probs = {"Like": 0.3, "Collect": 0.2, "Repost": 0.5}
        >>> behavior, biased_list, is_stable, unc = sample_behavior_watermark_uncertainty(
        ...     probs, seed=42, round_num=1, prob_bias=0.5, ratio=0.5,
        ...     BEHAVIOR_TYPES=['Like', 'Collect', 'Repost'], uncertainty_threshold=0.5
        ... )
        >>> print(f"Selected: {behavior}, Biased: {biased_list}, Stable: {is_stable}, Uncertainty: {unc}")
    """
    # Number of behaviors
    behavior_num = len(BEHAVIOR_TYPES)
    
    # Set random seed
    if seed is not None:
        # Combine seed and round number to create new seed
        combined_seed = seed + round_num
        random.seed(combined_seed)
    
    # Partition behaviors needing bias based on combined_seed and ratio
    # Calculate count of behaviors to bias
    biased_count = int(behavior_num * ratio)
    # Randomly select behaviors to bias
    add_logits_behavior_list = random.sample(BEHAVIOR_TYPES, biased_count)
    
    # Get behavior list and corresponding probability list
    behaviors = list(probabilities.keys())
    probs = list(probabilities.values())
    
    # Record original probabilities for later comparison
    original_probs = probs.copy()
    
    # Add probability bias to selected behaviors
    modified_probs = []
    for behavior, prob in zip(behaviors, probs):
        if behavior in add_logits_behavior_list:
            modified_probs.append(prob + prob_bias)
        else:
            modified_probs.append(prob)
    
    # Ensure probabilities sum to 1
    total = sum(modified_probs)
    if total != 1.0:
        modified_probs = [p/total for p in modified_probs]
    
    # Use random.choices for weighted random selection
    selected_behavior_watermark = random.choices(behaviors, weights=modified_probs, k=1)[0]
    
    # Calculate uncertainty
    # NOTE Method 1: Calculate difference between top 1 and top 2 modified probabilities
    # Sorting probabilities, difference between 1st and 2nd indicates confidence. Larger difference implies less uncertainty.
    # E.g., if max prob 0.8, 2nd 0.1, diff 0.7, selection is confident.
    sorted_probs = sorted(modified_probs, reverse=True)
    max_prob_diff = sorted_probs[0] - sorted_probs[1]
    
    # NOTE Method 2: Calculate max change between original and modified probabilities
    # Larger change implies watermark has larger impact, thus higher uncertainty.
    # E.g., original 0.2, modified 0.7, change 0.5, impact is high.
    prob_changes = [abs(m - o) for m, o in zip(modified_probs, original_probs)]
    max_prob_change = max(prob_changes)
    
    # NOTE Method 3: Calculate Entropy
    # Higher entropy means flatter distribution, higher uncertainty.
    # E.g., uniform [0.33, 0.33, 0.34], entropy ~1, very uncertain.
    # Concentrated [0.9, 0.05, 0.05], entropy ~0, very certain.
    entropy = -sum(p * math.log2(p) if p > 0 else 0 for p in modified_probs)
    normalized_entropy = entropy / math.log2(len(behaviors))  # Normalized entropy
    
    # Comprehensive uncertainty metric (can be adjusted as needed)
    uncertainty = (
        (1 - max_prob_diff) +  # Smaller prob diff means higher uncertainty
        max_prob_change +      # Larger prob change means higher uncertainty
        normalized_entropy     # Higher entropy means higher uncertainty
    ) / 3
    
    # Determine if watermark should be applied. Lower uncertainty means higher stability, more likely to start watermarking.
    is_stable = uncertainty < uncertainty_threshold
    
    return selected_behavior_watermark, add_logits_behavior_list, is_stable, uncertainty


# ==============================================================================
# ================ Differential Watermark Sampling ================
# ==============================================================================

def sample_behavior_differential(probabilities, bit_stream, bit_index, context_for_key=None, history_responses=None, seed=None, round_num=0):
    """
    Select behavior using the Differential Scheme Engine and embed secret information (New Differential Watermark Scheme)
    Adapter function for the new engine, supports dynamic key generation based on context.

    Args:
        probabilities (dict): Dictionary of behaviors and their corresponding probabilities.
        bit_stream (str): Secret information bit stream to embed.
        bit_index (int): Starting index in the bit stream.
        context_for_key (str, optional): Explicit context string for key generation (Recommended).
        history_responses (list, optional): [Deprecated] List of history responses, used only when context_for_key is None.
        seed (int, optional): Random seed (Fallback, current implementation uses context key).
        round_num (int, optional): Current round number.

    Returns:
        tuple: (Selected behavior, Target behavior list for detection, Number of bits embedded, Actual context used for key)
        
    Example:
        >>> probs = {"Like": 0.3, "Collect": 0.2, "Repost": 0.5}
        >>> context = "response1||response2"
        >>> behavior, targets, bits, ctx = sample_behavior_differential(probs, "10110", 0, context_for_key=context, round_num=1)
        >>> print(f"Selected: {behavior}, Targets: {targets}, Bits: {bits}")
    """
    # --- 1. Data Format Conversion (Adapt input for new engine) ---
    # Ensure fixed behavior order for consistent indexing
    behaviors = sorted(probabilities.keys())
    probs_list = [probabilities[b] for b in behaviors]
    
    # Convert to PyTorch Tensors
    # Force CPU to avoid CUDA initialization overhead in massive parallel runs
    device = 'cpu'
    probs_tensor = torch.tensor(probs_list, dtype=torch.float32, device=device)
    indices_tensor = torch.arange(len(behaviors), device=device)
    
    # --- 2. Initialize PRG (Dynamic Key Gen based on Context) ---
    # Decide context: Prefer context_for_key, else build from history_responses
    if context_for_key is not None:
        # Use explicit context string
        context_used = context_for_key
    else:
        # Backward compatibility: Build context from history_responses
        if history_responses is None:
            history_responses = []
        # Use sliding window (recent 3 responses) to build context
        window_size = 3
        recent_responses = history_responses[-window_size:] if len(history_responses) > 0 else []
        context_used = "||".join(recent_responses) if recent_responses else ""
    
    # === New Method: Key based on Explicit Context String ===
    key = generate_contextual_key([context_used])  # Pass as list for compatibility
    # nonce uses round number to ensure different random sequence per round
    nonce = str(round_num).encode('utf-8') 
    
    # === Old Method: Static Key based on Pre-shared Seed (Kept as comment) ===
    # If fallback to static key needed, uncomment below:
    # if seed is None:
    #     seed = 42
    # combined_seed_str = str(seed)
    # round_num_str = str(round_num)
    # key = combined_seed_str.encode('utf-8')
    # nonce = round_num_str.encode('utf-8')
    
    PRG = DRBG_Legacy(key, nonce)

    # --- 3. Call New Engine Core ---
    selected_idx_tensor, num_bits_embedded = differential_based_encoder(
        prob=probs_tensor,
        indices=indices_tensor,
        bit_stream=bit_stream,
        bit_index=bit_index,
        PRG=PRG
    )
    selected_idx = selected_idx_tensor.item()
    
    # --- 4. Convert Output and Generate "Target List" for Detection ---
    # Convert selected index ID back to behavior string
    selected_behavior = behaviors[selected_idx]
    
    # For detector (detect_watermark.py) to work, we need to recalculate which "bin" was selected.
    # Detector needs to know what the "target range" is.
    PRG_for_detection = DRBG_Legacy(key, nonce)  # Recreate PRG with same params
    
    indices_nonzero, bins, prob_new = differential_based_recombination(probs_tensor, indices_tensor)
    prob_new = prob_new / prob_new.sum()
    
    random_p = PRG_for_detection.generate_random(n=52)
    cdf = torch.cumsum(prob_new, dim=0)
    bin_indice_idx = torch.searchsorted(cdf, random_p).item()

    selected_bin_start_index = bins[bin_indice_idx]
    bin_content_indices = indices_nonzero[selected_bin_start_index:]
    
    # This is equivalent to "Green List" in old engine
    target_behavior_list = [behaviors[i] for i in bin_content_indices]

    if os.getenv("AGENTMARK_DEBUG_SAMPLER"):
        debug_payload = {
            "stage": "bin_select",
            "random_p": float(random_p),
            "cdf": [float(x) for x in cdf.tolist()],
            "bin_indice_idx": int(bin_indice_idx),
            "selected_bin_start_index": int(selected_bin_start_index),
            "bin_content": target_behavior_list,
        }
        print(f"[agentmark:sampler] {json.dumps(debug_payload, ensure_ascii=True)}")
    
    return selected_behavior, target_behavior_list, num_bits_embedded, context_used


# ==============================================================================
# ================ Differential Watermark Decoder ================
# ==============================================================================

def lsb_bits2int(bits):
    """
    Convert bit list to integer (LSB first)
    
    Args:
        bits (list): List of bits, e.g., [1, 0, 1] means binary 101 (LSB first)
        
    Returns:
        int: Corresponding integer value
        
    Example:
        >>> lsb_bits2int([1, 0, 1])  # LSB: 1*1 + 0*2 + 1*4 = 5
        5
    """
    result = 0
    for i, bit in enumerate(bits):
        result += bit * (2 ** i)
    return result


def lsb_int2bits(num, length):
    """
    Convert integer to bit list (LSB first)
    
    Args:
        num (int): Integer to convert
        length (int): Length of bit list
        
    Returns:
        list: List of bits (LSB first)
        
    Example:
        >>> lsb_int2bits(5, 3)  # 5 = 101(binary) -> [1, 0, 1] (LSB first)
        [1, 0, 1]
    """
    bits = []
    for _ in range(length):
        bits.append(num % 2)
        num //= 2
    return bits


def uni_cyclic_shift_dec(idx, n, PRG, precision=52):
    """
    Uniform cyclic shift decoder (Artifacts standard version)
    Corresponds to encoder uni_cyclic_shift_enc, extracts secret bits from selected index.
    
    Must optionally consistent with encoder PRG call order!
    
    Args:
        idx (int): Selected index position (relative position in the bin)
        n (int): Bin size
        PRG: Pseudo-random generator
        precision (int): Precision parameter
        
    Returns:
        str: Extracted bit string
    """
    if n == 1:
        PRG.generate_random(n=precision)
        return ''
    
    # Must be same as encoder, generate R first
    ptr = PRG.generate_random(n=precision)
    R = math.floor(ptr * n)
    
    k = math.floor(math.log2(n))
    t = n - 2**k
    
    # Reverse cyclic shift
    idx_sort = (idx - R) % n
    
    if idx_sort < 2**k - t:
        bits = lsb_int2bits(idx_sort, k)
        bits = "".join([str(_) for _ in bits])
        return bits
    else:
        s1 = idx_sort - 2**k + t
        s_last = s1 % 2
        
        bits = lsb_int2bits((s1 - s_last) // 2 + 2**k - t, k)
        bits = "".join([str(_) for _ in bits])
        
        if s_last == 0:
            return bits + '0'
        else:
            return bits + '1'


def differential_based_decoder(probabilities, selected_behavior, context_for_key=None, history_responses=None, round_num=0):
    """
    Differential Watermark Decoder - Extract embedded secret bits from selected behavior
    
    Args:
        probabilities (dict): Dictionary of behaviors and their corresponding probabilities
        selected_behavior (str): Actually selected behavior
        context_for_key (str, optional): Explicit context string used for key generation (Recommended to read from log)
        history_responses (list, optional): [Deprecated] List of history responses, used only when context_for_key is None
        round_num (int): Current round number (Must be same as encoding)
        
    Returns:
        str: Extracted bit string
        
    Example:
        >>> probs = {"Like": 0.3, "Collect": 0.2, "Repost": 0.5}
        >>> context = "response1||response2"
        >>> bits = differential_based_decoder(probs, "Repost", context_for_key=context, round_num=1)
        >>> print(f"Extracted bits: {bits}")
    """
    # --- 1. Data Format Conversion ---
    behaviors = sorted(probabilities.keys())
    probs_list = [probabilities[b] for b in behaviors]
    
    # Convert to PyTorch Tensors
    # Force CPU to avoid CUDA initialization overhead in massive parallel runs
    device = 'cpu'
    probs_tensor = torch.tensor(probs_list, dtype=torch.float32, device=device)
    indices_tensor = torch.arange(len(behaviors), device=device)
    
    # Find index of selected behavior
    try:
        selected_idx = behaviors.index(selected_behavior)
    except ValueError:
        print(f"Warning: Selected behavior '{selected_behavior}' not in behavior list")
        return ''
    
    prev_tensor = torch.tensor([selected_idx], device=device)
    
    # --- 2. Initialize PRG (Must be exactly same as encoding) ---
    # Decide context: Prefer context_for_key
    if context_for_key is not None:
        context_used = context_for_key
    else:
        # Backward compatibility: Build from history_responses
        if history_responses is None:
            history_responses = []
        window_size = 3
        recent_responses = history_responses[-window_size:] if len(history_responses) > 0 else []
        context_used = "||".join(recent_responses) if recent_responses else ""
    
    key = generate_contextual_key([context_used])
    nonce = str(round_num).encode('utf-8')
    PRG = DRBG_Legacy(key, nonce)
    
    # --- 3. Probability Recombination (Same as encoder) ---
    indices_nonzero, bins, prob_new = differential_based_recombination(probs_tensor, indices_tensor)
    
    if prob_new.sum() == 0:
        return ''
    
    prob_new = prob_new / prob_new.sum()
    
    # --- 4. Bin Sampling (Same as encoder) ---
    random_p = PRG.generate_random(n=52)
    cdf = torch.cumsum(prob_new, dim=0)
    bin_indice_idx = torch.searchsorted(cdf, random_p).item()
    
    selected_bin_start_index = bins[bin_indice_idx]
    bin_content = indices_nonzero[selected_bin_start_index:]
    
    # --- 5. Uniform Steganography Decoding ---
    # Find position of selected index in the bin
    try:
        idx_in_bin = (bin_content == prev_tensor.item()).nonzero().item()
    except (RuntimeError, ValueError):
        # If selected behavior not in bin, something went wrong
        print(f"Warning: Selected behavior not in expected bin, cannot decode")
        return ''
    
    # Use cyclic shift decoder to extract bits
    bits = uni_cyclic_shift_dec(idx=idx_in_bin, n=len(bin_content), PRG=PRG, precision=52)
    
    return bits
# ==============================================================================
# ================ Red-Green List Sampling Algorithms ================
# ==============================================================================

def sample_behavior_red_green(probabilities, context_for_key=None, history_responses=None, seed=None, round_num=0, gamma=0.5, delta=2.0):
    """
    Use Red-Green List strategy (KGW Style) for behavior sampling.
    
    Args:
        probabilities (dict): Behavior and their raw probabilities.
        context_for_key (str): Context info, used to generate random seed.
        history_responses (list): Backup context.
        seed (int): Backup seed.
        round_num (int): Round number, introducing time variance.
        gamma (float): Green list ratio (0.0 - 1.0). E.g., 0.5 means half behaviors are green list.
        delta (float): Logit bias value. Green list behaviors' logits will increase by delta.
        
    Returns:
        tuple: (Selected behavior, Green list, 0 bits, context_used)
    """
    # 1. Prepare Data
    behaviors = sorted(probabilities.keys())
    probs_list = [probabilities[b] for b in behaviors]
    # Force CPU to avoid CUDA initialization overhead in massive parallel runs
    device = 'cpu'
    
    # Convert probabilities to Logits (Inverse Softmax is not unique, assume raw Logits is log(p))
    # Add a small value to avoid log(0)
    epsilon = 1e-9
    probs_tensor = torch.tensor(probs_list, dtype=torch.float32, device=device)
    logits = torch.log(probs_tensor + epsilon)
    
    # 2. Generate Random Seed (Hash Context)
    if context_for_key is not None:
        context_used = context_for_key
    else:
        window_size = 3
        recent_responses = history_responses[-window_size:] if history_responses else []
        context_used = "||".join(recent_responses)
        
    # Generate hash as pseudo-random source
    # Note: To make red-green list independent for each behavior, typically hash(context + behavior)
    # But for efficiency and convenience of list return, here we generate a context-based random vector
    
    key = generate_contextual_key([context_used])
    nonce = str(round_num).encode('utf-8')
    PRG = DRBG_Legacy(key, nonce)
    
    # 3. Partition Red-Green List
    # Generate a random number in [0, 1] for each behavior
    # To ensure behavior order irrelevance, strictly should use hash(context + behavior_name)
    # But as long as behaviors list sort order is fixed, using PRG sequence is also deterministic and efficient
    
    green_list = []
    
    # Generate len(behaviors) random numbers
    random_vals = [PRG.generate_random(32) for _ in range(len(behaviors))]
    
    mask = torch.zeros_like(logits, device=device)
    
    for i, r_val in enumerate(random_vals):
        if r_val < gamma:
            # Enter Green List
            green_list.append(behaviors[i])
            mask[i] = 1.0
            
    # 4. Apply Watermark (Logit Bias)
    # Green List Logits increase by delta
    watermarked_logits = logits + (mask * delta)
    
    # 5. Sampling
    # Normalize using Softmax
    watermarked_probs = torch.softmax(watermarked_logits, dim=0)
    
    # Convert to Python list for weighted random
    final_probs = watermarked_probs.tolist()
    
    # Sampling
    # To maintain determinism, we can continue using PRG or use externally provided global seed
    # To match AgentMark style, use random.choices (depends on global seed or loop seed)
    # But considering sample_behavior_differential uses PRG efficiently, ideally PRG here too
    
    # Use next random number from PRG for sampling (Inverse Transform Sampling)
    rand_p = PRG.generate_random(52)
    cdf = torch.cumsum(watermarked_probs, dim=0)
    idx = torch.searchsorted(cdf, rand_p).item()
    idx = min(idx, len(behaviors) - 1) # Boundary protection
    
    selected_behavior = behaviors[idx]
    
    return selected_behavior, green_list, 0, context_used


# ==============================================================================
# ================ Rank-Based Watermark (Weakly Asymmetric) ================
# ==============================================================================

def sample_behavior_rank(
    probabilities: dict,
    bit_stream: str,
    bit_index: int,
    context_for_key: str = None,
    history_responses: list = None,
    round_num: int = 0,
    topk: int = None,
    watermark_key=None,
    sample_seed_prefix: bytes = b'sample',
    input_nonce: bytes = b'\x00' * 16,
):
    """
    Rank-based behavior level encoder (Adapter for RankStego).
    """
    # 1. Data format conversion
    behaviors = sorted(probabilities.keys())
    probs_list = [probabilities[b] for b in behaviors]
    device = 'cpu'
    probs_tensor = torch.tensor(probs_list, dtype=torch.float32, device=device)
    indices_tensor = torch.arange(len(behaviors), device=device)
    dist = Dist(probs_tensor, indices_tensor)

    # 2. Build context and key
    if context_for_key is not None:
        context_used = context_for_key
    else:
        if history_responses is None:
            history_responses = []
        window_size = 3
        recent = history_responses[-window_size:] if history_responses else []
        context_used = "||".join(recent) if recent else ""
    
    key = derive_contextual_watermark_key(context_used, watermark_key)
    # For RankStego, we use the Meteor DRBG seed = prefix + nonce + round
    seed = sample_seed_prefix + input_nonce + str(round_num).encode('utf-8')
    PRG = DRBG(key, seed)

    # 3. Encoding
    remaining_bits = bit_stream[bit_index:]
    
    # Get sorted order for top-k or target_list
    probs_sorted, indices_sorted = dist.get_sort(descending=True)
    
    if topk is not None and topk < len(dist):
        # top-k mode: if selected behavior is NOT in top-k, we can't embed.
        # But encoder must decide. Usually we only embed in top-k.
        total_topk = probs_sorted[:topk].sum().item()
        
        # We sample a random number to decide if we fall into top-k or tail
        # To maintain sync, we might need a separate PRG call or use one from current PRG.
        # Rank-based scheme usually expects to be in top-k.
        ptr = random.random() # Non-deterministic tail sampling is fine if decoder knows it's not in top-k
        
        if ptr >= total_topk:
            # Fall into tail (no embedding)
            tail_probs = probs_sorted[topk:]
            if tail_probs.sum() > 0:
                tail_probs = tail_probs / tail_probs.sum()
                j = torch.multinomial(tail_probs, 1).item()
            else:
                j = 0
            selected_idx = indices_sorted[topk + j].item()
            selected_behavior = behaviors[selected_idx]
            target_list = [behaviors[int(i)] for i in indices_sorted[:topk]]
            return selected_behavior, target_list, 0, context_used
        else:
            # Fall into top-k
            dist_topk = Dist(
                probs_sorted[:topk] / (total_topk + 1e-9),
                indices_sorted[:topk]
            )
            T, n_bits = RankEncStep(remaining_bits, dist_topk, PRG)
            selected_idx = T.item()
            selected_behavior = behaviors[selected_idx]
            target_list = [behaviors[int(i)] for i in indices_sorted[:topk]]
            return selected_behavior, target_list, n_bits, context_used
    else:
        # Full distribution mode
        T, n_bits = RankEncStep(remaining_bits, dist, PRG)
        selected_idx = T.item()
        selected_behavior = behaviors[selected_idx]
        target_list = [behaviors[int(i)] for i in indices_sorted]
        return selected_behavior, target_list, n_bits, context_used


def rank_based_decoder(
    probabilities: dict,
    selected_behavior: str,
    context_for_key: str = None,
    history_responses: list = None,
    round_num: int = 0,
    topk: int = None,
    watermark_key=None,
    sample_seed_prefix: bytes = b'sample',
    input_nonce: bytes = b'\x00' * 16,
) -> str:
    """
    Rank-based behavior level decoder (Weakly Asymmetric).
    """
    # 1. Data format conversion
    behaviors = sorted(probabilities.keys())
    probs_list = [probabilities[b] for b in behaviors]
    device = 'cpu'
    probs_tensor = torch.tensor(probs_list, dtype=torch.float32, device=device)
    indices_tensor = torch.arange(len(behaviors), device=device)

    # Find selected index
    try:
        selected_idx = behaviors.index(selected_behavior)
    except ValueError:
        return ''
    
    selected_tensor = torch.tensor([selected_idx], device=device)

    # 2. Key and PRG
    if context_for_key is not None:
        context_used = context_for_key
    else:
        if history_responses is None:
            history_responses = []
        window_size = 3
        recent = history_responses[-window_size:] if history_responses else []
        context_used = "||".join(recent) if recent else ""
    
    key = derive_contextual_watermark_key(context_used, watermark_key)
    seed = sample_seed_prefix + input_nonce + str(round_num).encode('utf-8')
    PRG = DRBG(key, seed)

    # 3. Decode
    dist = Dist(probs_tensor, indices_tensor)
    _, indices_sorted = dist.get_sort(descending=True)

    if topk is not None and topk < len(indices_sorted):
        rank_indices = indices_sorted[:topk]
        if selected_tensor.item() not in rank_indices:
            # Not in top-k, no bits embedded
            return ''
        return RankDecStep(selected_tensor, rank_indices, PRG)
    else:
        return RankDecStep(selected_tensor, indices_sorted, PRG)
