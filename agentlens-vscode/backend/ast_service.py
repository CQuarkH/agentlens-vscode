import json
import copy
import logging

logger = logging.getLogger(__name__)

from domain_models import AgentASTDocument

from cache_manager import get_robust_id


def build_tree_data(doc: AgentASTDocument) -> dict:
    all_rule_lengths = []
    for cat in doc.rootNode.children:
        for label in cat.children:
            for rule in label.children:
                all_rule_lengths.append(len(rule.content.text) if rule.content.text else 0)

    min_len = min(all_rule_lengths) if all_rule_lengths else 0
    max_len = max(all_rule_lengths) if all_rule_lengths else 1
    if min_len == max_len:
        max_len = min_len + 1

    MIN_WIDTH = 120
    MAX_WIDTH = 350

    tree = {
        "name": doc.repo_name,
        "group": "root",
        "width": doc.tree_width,
        "height": doc.tree_height,
        "color": doc.root_color,
        "border_width": 2,
        "details": doc.root_html_details,
        "children": []
    }

    for cat in doc.rootNode.children:
        if cat.count == 0:
            continue

        cat_node = {
            "name": cat.label,
            "group": "category",
            "width": cat.tree_width,
            "height": cat.tree_height,
            "color": cat.color,
            "border_width": cat.border_width,
            "details": cat.html_details,
            "metrics": {
                "lbls": cat.total_labels,
                "rls": cat.total_rules,
                "code": round(cat.code_ratio, 2)
            },
            "children": []
        }

        for label in cat.children:
            fre_score = getattr(label, 'computed_fre_score', 50.0)
            label_node = {
                "name": label.label,
                "group": "label",
                "width": label.tree_width,
                "height": label.tree_height,
                "color": label.color,
                "border_width": label.border_width,
                "details": label.html_details,
                "metrics": {
                    "rls": label.total_rules,
                    "fre": round(fre_score, 1),
                    "code": round(label.code_ratio, 2)
                },
                "children": []
            }

            for rule in label.children:
                text_len = len(rule.content.text) if rule.content.text else 0
                normalized_width = MIN_WIDTH + ((text_len - min_len) / (max_len - min_len)) * (MAX_WIDTH - MIN_WIDTH)

                label_node["children"].append({
                    "name": rule.short_label,
                    "group": "rule",
                    "width": round(normalized_width),
                    "height": rule.tree_height,
                    "color": label.color,
                    "border_width": 1.5,
                    "raw_text": rule.content.text,
                    "details": rule.html_details,
                    "strength": rule.metadata.strength,
                    "value": 1,
                    "metrics": {
                        "len": text_len,
                        "sym": rule.special_chars_count
                    }
                })

            cat_node["children"].append(label_node)

        tree["children"].append(cat_node)

    return tree


def parse_commit_tree(json_data: dict, commit_sha: str, repo_name: str) -> dict | None:
    try:
        doc = AgentASTDocument.model_validate(json_data)
    except Exception as e:
        logger.error(f"Failed to validate JSON for commit {commit_sha}: {e}")
        return None

    max_rule_len = 1
    for cat in doc.rootNode.children:
        for label in cat.children:
            for rule in label.children:
                text = rule.content.text if (hasattr(rule, 'content') and rule.content) else ""
                max_rule_len = max(max_rule_len, len(text))

    tree = {
        "id": "root", "name": doc.repo_name, "group": "root",
        "color": getattr(doc, 'root_color', "#e2e8f0"),
        "details": getattr(doc, 'root_html_details', ""),
        "width": getattr(doc, 'tree_width', 220),
        "height": getattr(doc, 'tree_height', 60),
        "children": []
    }

    for cat in doc.rootNode.children:
        if getattr(cat, 'count', -1) == 0:
            continue

        cat_name = cat.label
        cat_id = f"cat_{cat_name}"
        cat_color = getattr(cat, 'color', "#94a3b8")

        cat_node = {
            "id": cat_id, "name": cat_name, "group": "category", "cat_name": cat_name,
            "color": cat_color, "details": getattr(cat, 'html_details', ""),
            "width": getattr(cat, 'tree_width', 150),
            "height": getattr(cat, 'tree_height', 50),
            "border_width": getattr(cat, 'border_width', 2.0),
            "metrics": {
                "lbls": getattr(cat, 'total_labels', 0),
                "rls": getattr(cat, 'total_rules', 0),
                "code": round(getattr(cat, 'code_ratio', 0.0), 2)
            },
            "children": []
        }

        for label in cat.children:
            label_name = label.label
            label_id = f"lbl_{cat_name}_{label_name}"
            label_color = getattr(label, 'color', cat_color)

            label_node = {
                "id": label_id, "name": label_name, "group": "label", "cat_name": cat_name,
                "color": label_color, "details": getattr(label, 'html_details', ""),
                "width": getattr(label, 'tree_width', 150),
                "height": getattr(label, 'tree_height', 40),
                "border_width": getattr(label, 'border_width', 2.0),
                "metrics": {
                    "rls": getattr(label, 'total_rules', 0),
                    "fre": round(getattr(label, 'computed_fre_score', 0.0), 1),
                    "code": round(getattr(label, 'code_ratio', 0.0), 2)
                },
                "children": []
            }

            for rule in label.children:
                text = rule.content.text if (hasattr(rule, 'content') and rule.content) else ""
                rule_label = getattr(rule, 'short_label', None)
                if not rule_label or rule_label == "Rule":
                    rule_label = text.strip().split('\n')[0][:60] + "..." if text else "Empty Rule"

                rule_id = f"rule_{cat_name}_{label_name}_{get_robust_id(text)}"
                text_len = len(text)

                min_w = 180
                max_w = 550
                dyn_width = int(min_w + (text_len / max_rule_len) * (max_w - min_w)) if max_rule_len > 0 else min_w

                label_node["children"].append({
                    "id": rule_id, "name": rule_label, "group": "rule", "cat_name": cat_name,
                    "color": label_color, "raw_text": text,
                    "details": getattr(rule, 'html_details', ""),
                    "width": dyn_width,
                    "height": getattr(rule, 'tree_height', 36),
                    "border_width": 2.0,
                    "metrics": {
                        "len": text_len, "sym": getattr(rule, 'special_chars_count', 0)
                    }
                })

            if label_node["children"]:
                cat_node["children"].append(label_node)
        if cat_node["children"]:
            tree["children"].append(cat_node)

    return tree


def get_flat_nodes(tree_node, parent_id=None):
    nodes = {tree_node['id']: {'node': tree_node, 'parent_id': parent_id}}
    for child in tree_node.get('children', []):
        nodes.update(get_flat_nodes(child, tree_node['id']))
    return nodes


def mark_deleted_recursively(node):
    node['diff_status'] = 'deleted'
    for child in node.get('children', []):
        mark_deleted_recursively(child)


def inject_diff_states(prev_tree, curr_tree):
    if not prev_tree:
        curr_nodes = get_flat_nodes(curr_tree)
        for val in curr_nodes.values():
            val['node']['diff_status'] = 'kept'
        return curr_tree

    curr_merged = copy.deepcopy(curr_tree)
    prev_nodes = get_flat_nodes(prev_tree)
    curr_nodes = get_flat_nodes(curr_merged)

    for nid, val in curr_nodes.items():
        if nid not in prev_nodes:
            val['node']['diff_status'] = 'added'
        else:
            val['node']['diff_status'] = 'kept'

    for nid, prev_val in prev_nodes.items():
        if nid not in curr_nodes:
            parent_id = prev_val['parent_id']
            if parent_id and parent_id in curr_nodes:
                ghost_node = copy.deepcopy(prev_val['node'])
                mark_deleted_recursively(ghost_node)
                curr_nodes[parent_id]['node'].setdefault('children', []).append(ghost_node)

    return curr_merged


def extract_timeline_data(cached_commits: list[dict]) -> dict:
    diff_commits = []
    prev_tree = None

    cum_rule_changes = 0
    cum_label_changes = 0
    cat_cum_stats = {}

    for idx, entry in enumerate(cached_commits):
        merged_tree = inject_diff_states(prev_tree, entry["tree"])

        rules_changed_here = 0
        labels_changed_here = 0
        cat_changed_here = {}

        global_added = 0
        global_deleted = 0
        cat_delta_here = {}

        if idx > 0:
            flat_merged = get_flat_nodes(merged_tree)
            for val in flat_merged.values():
                node = val['node']
                status = node.get('diff_status')
                group = node.get('group')
                cat_name = node.get('cat_name')

                if status in ('added', 'deleted'):
                    if group == 'rule':
                        rules_changed_here += 1
                        if cat_name:
                            cat_changed_here.setdefault(cat_name, {'rules': 0, 'labels': 0})['rules'] += 1
                    elif group == 'label':
                        labels_changed_here += 1
                        if cat_name:
                            cat_changed_here.setdefault(cat_name, {'rules': 0, 'labels': 0})['labels'] += 1

                    if group in ('rule', 'label'):
                        if cat_name not in cat_delta_here:
                            cat_delta_here[cat_name] = {'added': 0, 'deleted': 0}

                        if status == 'added':
                            global_added += 1
                            if cat_name:
                                cat_delta_here[cat_name]['added'] += 1
                        elif status == 'deleted':
                            global_deleted += 1
                            if cat_name:
                                cat_delta_here[cat_name]['deleted'] += 1

            cum_rule_changes += rules_changed_here
            cum_label_changes += labels_changed_here

            for cat, diffs in cat_changed_here.items():
                if cat not in cat_cum_stats:
                    cat_cum_stats[cat] = {'rules': 0, 'labels': 0}
                cat_cum_stats[cat]['rules'] += diffs['rules']
                cat_cum_stats[cat]['labels'] += diffs['labels']

        diff_commits.append({
            "index": idx,
            "commit": entry["commit"],
            "tree": merged_tree,
            "stats": {
                "global": {
                    "cum_rules": cum_rule_changes,
                    "cum_labels": cum_label_changes
                },
                "by_category": copy.deepcopy(cat_cum_stats),
                "delta": {
                    "global": {
                        "added": global_added,
                        "deleted": global_deleted
                    },
                    "by_category": copy.deepcopy(cat_delta_here)
                }
            }
        })
        prev_tree = entry["tree"]

    return {"commits": diff_commits}
