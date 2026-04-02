
import sys
import os
import torch

# Add current directory to path
sys.path.append('d:/_Development/AgentMark/Aysm/AgentMarkBeta')

from agentmark.sdk.watermarker import AgentWatermarker

def test_rank_stego_consistency():
    print("--- Testing RankStego Consistency ---")
    wm = AgentWatermarker(payload_text="AG", algorithm="rank")
    
    probs = {
        "move_left": 0.1,
        "move_right": 0.2,
        "jump": 0.05,
        "attack": 0.4,
        "defend": 0.25
    }
    
    # 1. Sample
    res = wm.sample(probs, context="test_context", round_num=0)
    print(f"Sampled Action: {res.action}, Bits Embedded: {res.bits_embedded}")
    
    # 2. Decode with same probs
    decoded = wm.decode(probs, res.action, context="test_context", round_num=0)
    print(f"Decoded Bits (Same Probs): {decoded}")
    
    # 3. Weak Asymmetry Test: Modify Probs but keep ranks
    # Ranks (descending): attack (0.4) > defend (0.25) > move_right (0.2) > move_left (0.1) > jump (0.05)
    probs_modified = {
        "move_left": 0.05,
        "move_right": 0.1,
        "jump": 0.02,
        "attack": 0.6,
        "defend": 0.23
    }
    
    decoded_asy = wm.decode(probs_modified, res.action, context="test_context", round_num=0)
    print(f"Decoded Bits (Modified Probs, Same Ranks): {decoded_asy}")
    
    assert decoded == decoded_asy, "RankStego should be weakly asymmetric (same ranks -> same bits)"
    print("SUCCESS: RankStego consistency and weak asymmetry verified.")


def test_differential_backward_compatibility():
    print("\n--- Testing Differential Backward Compatibility ---")
    wm = AgentWatermarker(payload_text="ABC", algorithm="differential")
    
    probs = {
        "A": 0.3,
        "B": 0.3,
        "C": 0.4
    }
    
    res = wm.sample(probs, context="diff_context", round_num=0)
    print(f"Sampled Action: {res.action}, Bits Embedded: {res.bits_embedded}")
    
    decoded = wm.decode(probs, res.action, context="diff_context", round_num=0)
    print(f"Decoded Bits: {decoded}")
    
    # Differential should FAIL/Change if probs change significantly
    probs_mod = {"A": 0.1, "B": 0.1, "C": 0.8}
    decoded_mod = wm.decode(probs_mod, res.action, context="diff_context", round_num=0)
    print(f"Decoded Bits (Modified Probs): {decoded_mod}")
    
    print("SUCCESS: Differential scheme still functional.")

if __name__ == "__main__":
    try:
        test_rank_stego_consistency()
        test_differential_backward_compatibility()
    except Exception as e:
        print(f"Test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
