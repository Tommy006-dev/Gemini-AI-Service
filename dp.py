import sqlite3

def init_db():
    # Kết nối đến file database (nếu chưa có, SQLite sẽ tự động tạo file blog.db)
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()

    # Thực thi câu lệnh SQL tạo bảng
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blog_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        seo_description TEXT NOT NULL,
        html_content TEXT NOT NULL,
        tags TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("Đã khởi tạo Database 'blog.db' và bảng 'blog_posts' thành công!")

if __name__ == '__main__':
    init_db()