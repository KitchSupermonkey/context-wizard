"""
Global search across all tables in the Feishu Base.
Scans every table using `lark-cli base +record-search` on `标签` and `核心结论` fields,
merges results with project metadata, sorts by `最后更新` descending, and outputs JSON.

Usage:
    python scripts/global_search.py "关键词"
    python scripts/global_search.py "关键词" /path/to/config.json
"""
import sys
import json
import os

# Cross-platform: Windows console defaults to GBK, force UTF-8 for emoji output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from cli import LarkCLI


def global_search(query, config_path=None):
    """
    Search across all tables in the Base for records matching the query keyword.
    
    Args:
        query: Search keyword string.
        config_path: Optional path to config.json. Defaults to scripts/config.json.
    
    Returns:
        JSON string with {"query": ..., "count": N, "records": [...]}.
    """
    cli = LarkCLI(config_path=config_path)
    app_token = cli.get_base_token()
    if not app_token:
        return json.dumps(
            {"error": "❌ 未配置 Base Token。请先运行: python scripts/init_base.py"},
            ensure_ascii=False
        )

    # List all tables in the Base
    try:
        tables_output = cli.run(["base", "+table-list", "--base-token", app_token])
        tables_data = json.loads(tables_output)
        tables = tables_data.get("data", {}).get("tables", [])
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON from table-list: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to list tables: {str(e)}"}, ensure_ascii=False)

    if not tables:
        return json.dumps({"query": query, "count": 0, "records": []}, ensure_ascii=False)

    # Search payload — search across all user-facing fields
    search_payload = json.dumps({
        "keyword": query,
        "search_fields": ["实体名称", "文档类型", "核心结论", "关键时间", "涉及人员", "标签"]
    })

    all_records = []

    for table in tables:
        table_id = table.get("id")
        table_name = table.get("name", "Unknown")

        if not table_id:
            continue

        try:
            res = cli.run([
                "base", "+record-search",
                "--base-token", app_token,
                "--table-id", table_id,
                "--json", search_payload
            ])
            try:
                data = json.loads(res).get("data", {})
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON parse error for table '{table_name}': {e}", file=sys.stderr)
                continue
            fields = data.get("fields", [])
            rows = data.get("data", [])

            for row in rows:
                # Build record from parallel fields/rows arrays
                record = {}
                for i, field_name in enumerate(fields):
                    if i < len(row):
                        val = row[i]
                        # Handle array fields (select types) → convert to string
                        if isinstance(val, list):
                            val = ", ".join(str(v) for v in val)
                        if val is not None:
                            record[field_name] = val

                # Attach metadata
                record["_project_name"] = table_name
                record["_table_id"] = table_id
                all_records.append(record)

        except Exception as e:
            # Skip tables that fail (might not support record-search or empty)
            print(f"[WARN] Failed to search table '{table_name}' ({table_id}): {e}", file=sys.stderr)
            continue

    # Sort by `最后更新` descending
    all_records.sort(key=lambda x: x.get("最后更新", ""), reverse=True)

    return json.dumps({
        "query": query,
        "count": len(all_records),
        "records": all_records
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/global_search.py <keyword> [config_path]")
        sys.exit(1)

    query = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else None

    print(global_search(query, config_path=config_path))
