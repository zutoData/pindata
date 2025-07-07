import uuid
from typing import Dict, Any, List, Union
import json
from .tools import get_operator_content,get_operator_descriptions
 

def combine_pipeline_result(
        result: Dict[str, Any],
        task_results_history: List
) -> Dict[str, Any]:
    edges = result.get("edges")
    if not isinstance(edges, list):
        return result

    nodes_info: Union[List[Dict[str, Any]], Dict[str, str], None] = None
    for past in reversed(task_results_history):
        if "ContentSubType" in past:
            if past["ContentSubType"] == "MIXTURE":
                nodes_info = get_operator_descriptions()
            else:
                nodes_info = get_operator_content("", past)
            break

    # Handle case when nodes_info is None or not a list/dict
    if nodes_info is None:
        return result
    id_map: Dict[str, Dict[str, Any]] = {}
    # Case 1: nodes_info is a dictionary of operator descriptions (for MIXTURE)
    if isinstance(nodes_info, dict):
        for node_id, (op_name, description) in enumerate(nodes_info.items(), start=1):
            key = f"node{node_id}"
            id_map[key] = {
                "node": node_id,
                "name": op_name,
                "description": description
            }
    # Case 2: nodes_info is a list of node dictionaries
    elif isinstance(nodes_info, list):
        for node_dict in nodes_info:
            if not isinstance(node_dict, dict):
                continue
            node_id = node_dict.get("node")
            if isinstance(node_id, int):
                key = f"node{node_id}"
                id_map[key] = node_dict

    def normalize(nid: Any) -> Union[str, None]:
        if isinstance(nid, int):
            return f"node{nid}"
        if isinstance(nid, str):
            return nid if nid.startswith("node") else f"node{nid}"
        return None

    seen_ids = set()
    out_nodes: List[Dict[str, Any]] = []
    normalized_edges: List[Dict[str, str]] = []

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = normalize(edge.get("source"))
        tgt = normalize(edge.get("target"))
        if src is None or tgt is None:
            continue
        normalized_edges.append({"source": src, "target": tgt})
        for rid in (src, tgt):
            node_dict = id_map.get(rid)
            if not node_dict:
                continue
            node_id = node_dict["node"]
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            filtered = {
                k: v
                for k, v in node_dict.items()
                if k not in ("input", "output", "node")
            }
            filtered["id"] = rid
            out_nodes.append(filtered)

    new_result = dict(result)
    new_result["nodes"] = out_nodes
    new_result["edges"] = normalized_edges
    new_result["name"] = f"{uuid.uuid4()}_pipeline"
    return new_result

if __name__ == "__main__":
    pass