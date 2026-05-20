"""
Check if a table exists in the Base by name.
If not, create a new table with the standard schema (8 fields).
Returns the table_id.
"""
import sys
import json
import os
from cli import LarkCLI

def get_or_create_table(app_token, project_name, table_name=None):
    """
    Check if a project table exists. If not, create it.
    project_name: 主项目名（用于匹配/创建表）
    table_name: 可选，如果不提供则使用 project_name
    """
    if table_name is None:
        table_name = project_name
    
    cli = LarkCLI()
    
    # Auto-load base_token from config if not provided
    if not app_token:
        app_token = cli.get_base_token()
        if not app_token:
            raise Exception("❌ Base token not found. Please run 'python scripts/init_base.py' to initialize.")
    
    # 1. List tables
    try:
        output = cli.run(["base", "+table-list", "--base-token", app_token])
        data = json.loads(output)
        tables = data.get("data", {}).get("tables", [])
    except Exception:
        tables = []

    # 2. Find table. Prefer exact matches before partial matches so a broad
    # project like "甄选" is not swallowed by "甄选625方案讨论会".
    for t in tables:
        table_name_actual = t.get("name", "")
        if table_name == table_name_actual:
            print(f"🔍 Found existing table: {table_name_actual} (ID: {t['id']})")
            return t["id"]
    if len(table_name) >= 4:
        for t in tables:
            table_name_actual = t.get("name", "")
            if table_name in table_name_actual or table_name_actual in table_name:
                print(f"🔍 Found existing table: {table_name_actual} (ID: {t['id']})")
                return t["id"]

    # 3. Create table if missing
    print(f"✨ Table not found. Creating new table: {table_name}...")
    
    # Create table first
    create_output = cli.create_table(app_token, table_name)
    create_data = json.loads(create_output)
    table_id = create_data.get("data", {}).get("table", {}).get("id")
    
    if not table_id:
        raise Exception("Failed to get table_id after creation")

    print(f"✅ Created table: {table_id}")
    
    # 4. Add Fields to the new table
    fields_to_create = [
        ("实体名称", "text"),
        ("实体类型", "select", ["项目", "客户", "合作伙伴", "产品"]),
        ("文档类型", "select", ["会议纪要", "需求文档", "复盘报告", "运营方案", "合作协议", "数据分析", "竞品调研", "其他"]),
        ("核心结论", "text"),
        ("关键时间", "text"),
        ("涉及人员", "text"),
        ("标签", "text"),
        ("关联文档", "url"),
        ("文档 Token", "text"),
        ("最后更新", "datetime")
    ]
    
    print("🔧 Configuring fields...")
    for field_info in fields_to_create:
        name = field_info[0]
        type_id = field_info[1]
        opts = field_info[2] if len(field_info) > 2 else None
        cli.create_field(app_token, table_id, type_id, name, options=opts)

    # 5. Auto-create dashboard for the new table
    print("📊 Creating project dashboard...")
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "create_dashboard.py"), app_token, table_name],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", shell=(sys.platform == "win32")
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr and "already exists" not in result.stderr.lower():
            print(f"[WARN] {result.stderr.strip()}")
    except Exception as e:
        print(f"[WARN] Dashboard creation skipped (non-critical): {e}")

    return table_id

if __name__ == "__main__":
    # Support both explicit argument and auto-config
    if len(sys.argv) < 2:
        print("Usage: python get_or_create_table.py <project_name> [app_token]")
        sys.exit(1)
    
    # If first arg looks like a token (alphanumeric, ~20 chars), use old mode.
    # Otherwise assume it's the project name.
    first_arg = sys.argv[1]
    if len(first_arg) > 15 and first_arg.isalnum():
        app_token = first_arg
        project_name = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        project_name = first_arg
        app_token = sys.argv[2] if len(sys.argv) > 2 else None
        
    try:
        tid = get_or_create_table(app_token, project_name)
        print(tid)
    except Exception as e:
        print(f"Error: {e}")
