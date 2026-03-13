#!/bin/bash
# 使用docker exec导入数据的脚本

set -e

echo "🚀 通过Docker导入arXiv元数据"
echo "============================"

# 创建临时导入脚本
cat > /tmp/import_data.py << 'PYTHON_SCRIPT'
import json
import psycopg2
import sys
from tqdm import tqdm

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}

def parse_line(line):
    try:
        data = json.loads(line)
        year = None
        if data.get("versions"):
            created = data["versions"][0].get("created", "")
            try:
                year = int(created.split()[-3]) if len(created.split()) > 3 else None
            except:
                pass
        if year is None and data.get("update_date"):
            try:
                year = int(data["update_date"].split("-")[0])
            except:
                pass

        categories = data.get("categories", "").split()
        authors = []
        if data.get("authors_parsed"):
            for author in data["authors_parsed"]:
                if isinstance(author, list) and len(author) >= 2:
                    authors.append(f"{author[1]} {author[0]}".strip())

        return {
            "id": data.get("id"),
            "title": data.get("title", "").strip()[:500],  # 限制长度
            "authors": authors,
            "abstract": data.get("abstract", "").strip()[:2000],
            "categories": categories,
            "year": year,
            "doi": data.get("doi"),
            "journal_ref": data.get("journal-ref")
        }
    except:
        return None

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    batch = []
    imported = 0
    max_papers = 10000
    batch_size = 500

    print(f"开始导入 {max_papers} 条记录...")

    with open("/data/arxiv-metadata-oai-snapshot.json", "r", encoding="utf-8") as f:
        with tqdm(total=max_papers, desc="导入") as pbar:
            for line in f:
                if imported >= max_papers:
                    break

                paper = parse_line(line)
                if paper and paper["id"]:
                    batch.append(paper)

                    if len(batch) >= batch_size:
                        args_str = ','.join(cursor.mogrify(
                            "(%s, %s, %s, %s, %s, %s, %s, %s)",
                            (p["id"], p["title"], p["authors"], p["abstract"],
                             p["categories"], p["year"], p["doi"], p["journal_ref"])
                        ).decode('utf-8') for p in batch)

                        cursor.execute(f"""
                            INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                            VALUES {args_str} ON CONFLICT (id) DO NOTHING
                        """)
                        conn.commit()

                        imported += len(batch)
                        pbar.update(len(batch))
                        batch = []

            # 最后一批
            if batch:
                args_str = ','.join(cursor.mogrify(
                    "(%s, %s, %s, %s, %s, %s, %s, %s)",
                    (p["id"], p["title"], p["authors"], p["abstract"],
                     p["categories"], p["year"], p["doi"], p["journal_ref"])
                ).decode('utf-8') for p in batch)

                cursor.execute(f"""
                    INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                    VALUES {args_str} ON CONFLICT (id) DO NOTHING
                """)
                conn.commit()
                imported += len(batch)
                pbar.update(len(batch))

    cursor.execute("SELECT COUNT(*) FROM papers")
    count = cursor.fetchone()[0]
    print(f"\n✅ 导入完成！总计 {count} 条记录")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
PYTHON_SCRIPT

# 复制数据文件到容器
# 先检查文件是否存在
if [ ! -f "/home/cyh/下载/arxiv-metadata-oai-snapshot.json" ]; then
    echo "❌ 错误: 找不到数据文件"
    exit 1
fi

# 创建挂载点并复制
sudo docker-compose exec -T postgres mkdir -p /data 2>/dev/null || true
echo "📁 复制数据文件到容器..."
sudo docker cp /home/cyh/下载/arxiv-metadata-oai-snapshot.json valiref-pgvector:/data/

# 复制导入脚本
echo "📄 复制导入脚本..."
sudo docker cp /tmp/import_data.py valiref-pgvector:/tmp/

# 在容器内安装依赖并运行
echo "📦 安装依赖..."
sudo docker-compose exec -T postgres bash -c "pip install psycopg2-binary tqdm -q 2>/dev/null || apt-get update && apt-get install -y python3-psycopg2 python3-tqdm -qq"

echo "🚀 开始导入..."
sudo docker-compose exec -T postgres python3 /tmp/import_data.py

echo ""
echo "✅ 导入完成！"
