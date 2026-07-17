import pymysql
from sshtunnel import SSHTunnelForwarder

def check():
    ssh_host = '13.201.224.132'
    ssh_user = 'ubuntu'
    sql_user = 'marketplace_admin'
    sql_password = 'SuperSecretDBPassword123'
    db_name = 'rocks'
    pem_file = '../LambdaFinancials.pem'
    
    tunnel = SSHTunnelForwarder(
        (ssh_host, 22),
        ssh_username=ssh_user,
        ssh_pkey=pem_file,
        remote_bind_address=('localhost', 3306)
    )
    tunnel.start()
    connection = pymysql.connect(
        host='127.0.0.1',
        user=sql_user,
        password=sql_password,
        database=db_name,
        port=tunnel.local_bind_port,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM product_reviews")
        rows = cursor.fetchall()
        print(f"Total reviews: {len(rows)}")
        for r in rows:
            print(r)
            
    connection.close()
    tunnel.stop()

if __name__ == "__main__":
    check()
