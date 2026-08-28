#!/usr/bin/env python3
"""Gnostic traverse convergence test."""

from kaskade.gnostic.traverse import gnostic_traverse


def test_traverse_finds_hub():
    edges = [
        {"src_node_id": "a", "dst_node_id": "hub", "edge_type": "TAGGED_WITH"},
        {"src_node_id": "b", "dst_node_id": "hub", "edge_type": "TAGGED_WITH"},
        {"src_node_id": "c", "dst_node_id": "hub", "edge_type": "ABOUT"},
    ]
    out = gnostic_traverse(seeds=["a", "b"], edges=edges, hops=2)
    assert out["gnostic_moment"] == "hub"
