
import sys
from pathlib import Path

# 添加路径
sys.path.append(str(Path.cwd()))

try:
    from backend.db.session import get_session_factory, init_database
    from sqlalchemy import text
    
    print("正在测试数据库连接...")
    init_database()
    factory = get_session_factory()
    with factory() as session:
        result = session.execute(text("SELECT 1")).scalar()
        if result == 1:
            print("SUCCESS: 数据库连接正常！")
        else:
            print("ERROR: 数据库查询返回异常结果。")
except Exception as e:
    print(f"FAILED: 数据库连接失败！报错信息: {e}")
